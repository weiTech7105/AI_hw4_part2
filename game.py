"""
亞洲人生存大挑戰（七關版）

關卡設計：
1. 出生：決定性別（固定規則）
2. 大學志願：選科系（關鍵字 + 固定評分）
3. 第一份工作：三條人生起跑線（固定三選一 + 固定評分）
4. 結婚對象：三種對象（固定三選一 + 固定評分）
5. 生小孩與否（固定三選一 + 固定評分）
6. 過年大拷問：AI 隨機生成長輩問題，AI 判斷難度，AI 分析玩家回答風格，
   程式根據「難度 + 是否答得剛剛好（balanced）」做硬性扣分 / 加分。
7. 親戚稱謂魔王關：AI 生成親戚稱謂難題 + 正解 + 難度，
   程式根據「難度 + 玩家是否答對」做硬性扣分 / 加分。

共同規則：
- 初始 HP = 100。
- 每關至少寫下一則「人生小筆記」（B + C 風格：有點靠北又是短句金句）。
- 遊戲中任一處輸入：note → 顯示目前的人生小筆記清單。
- HP 歸零 → Game Over。
- 撐過七關且 HP > 0 → 視為通關。
"""

import json
import time
import pathlib
from typing import Dict, Any, List

import openai  # 請先 pip install openai

# ======== 基本設定 ========

MODEL_NAME = "gpt-3.5-turbo"  # 若學校有指定模型，可改這裡

MAX_TURNS = 7
INITIAL_HP = 100

CHAPTERS = [
    {"id": 1, "name": "出生：決定性別開局"},
    {"id": 2, "name": "大學志願：未來科系選擇"},
    {"id": 3, "name": "第一份工作：三條人生起跑線"},
    {"id": 4, "name": "結婚對象：誰陪你一起被比較"},
    {"id": 5, "name": "生小孩：要不要生，生幾個"},
    {"id": 6, "name": "過年大拷問：長輩玄學問候術"},
    {"id": 7, "name": "親戚稱謂魔王關：你到底叫什麼"},
]

OUTPUT_DIR = pathlib.Path("lab2.2_output")
STATE_DIR = OUTPUT_DIR / "state"
STATE_PATH = STATE_DIR / "save_1.json"
SUMMARY_PATH = OUTPUT_DIR / "summary_1.txt"

# 難度 → 固定評分標準
DIFFICULTY_SCORES = {
    "low":     {"correct": 5,  "wrong": -55},
    "medium":  {"correct": 10,  "wrong": -45},
    "high":    {"correct": 15, "wrong": -35},
    "extreme": {"correct": 20, "wrong": -25},
}

# ======== OpenAI 基本封裝 ========

def setup_openai():
    """啟動程式時詢問 API Key，直接設定給 openai。"""
    print("請輸入你的 OpenAI API Key：")
    api_key = input("> ").strip()
    if not api_key:
        raise RuntimeError("你沒有輸入 API Key，遊戲還沒開始就先 GG 了。")
    openai.api_key = api_key
    print("\n✔ API Key 載入成功。來體驗一輪七關版《亞洲人生存大挑戰》吧。\n")


def call_llm(system_prompt: str,
             user_prompt: str,
             temperature: float = 0.7) -> str:
    """呼叫 LLM，回傳文字內容（不做 JSON 解析）。"""
    resp = openai.ChatCompletion.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
    )
    return resp["choices"][0]["message"]["content"].strip()


def call_llm_json(system_prompt: str,
                  user_prompt: str,
                  temperature: float = 0.7) -> Dict[str, Any]:
    """
    呼叫 LLM，要求輸出為 JSON。
    若第一次 parse 失敗，嘗試從字串中抓出 JSON 區段再 parse。
    """
    content = call_llm(system_prompt, user_prompt, temperature)

    # 先嘗試直接解析
    try:
        return json.loads(content)
    except Exception:
        pass

    # 嘗試從字串中抓出 JSON 區段
    start = content.find("{")
    end = content.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            json_str = content[start:end + 1]
            return json.loads(json_str)
        except Exception:
            pass

    raise ValueError(f"無法解析為合法 JSON，請檢查 LLM 輸出：\n{content}")


# ======== 遊戲狀態與工具 ========

def init_game_state() -> Dict[str, Any]:
    """初始化遊戲狀態"""
    return {
        "hp": INITIAL_HP,
        "turn": 1,
        "notes": [],           # 人生小筆記清單
        "logs": [],            # 每關詳細紀錄
        "world_seed": int(time.time()),
        "end_flag": None,      # "win" / "lose" / None
    }


def ensure_output_dirs():
    """確保 lab2.2_output 與 state 子資料夾存在"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def save_state(state: Dict[str, Any]):
    """把整個遊戲狀態存成 JSON 檔"""
    ensure_output_dirs()
    with STATE_PATH.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    print(f"\n[系統] 遊戲狀態已儲存到：{STATE_PATH}")


def save_summary(review: str):
    """儲存遊戲人生回顧文字到 summary_1.txt"""
    ensure_output_dirs()
    with SUMMARY_PATH.open("w", encoding="utf-8") as f:
        f.write(review)
    print(f"[系統] 人生回顧已儲存到：{SUMMARY_PATH}")


def show_notes(state: Dict[str, Any]):
    """列出目前累積的人生小筆記清單"""
    print("\n===== 目前累積的人生小筆記 =====")
    if not state["notes"]:
        print("暫時還沒有，但光是活到這裡就已經很不容易了。")
    else:
        for idx, note in enumerate(state["notes"], start=1):
            print(f"{idx}. {note}")
    print("====================================\n")


def get_player_input(prompt: str,
                     state: Dict[str, Any],
                     allow_empty: bool = False,
                     default_text: str = "") -> str:
    """
    共用輸入工具：
    - 玩家輸入 note → 顯示人生小筆記後重新要求輸入
    - 若 allow_empty=False，空字串會請玩家再試一次
    """
    while True:
        ans = input(prompt).strip()
        if ans.lower() == "note":
            show_notes(state)
            continue
        if not ans:
            if allow_empty:
                return default_text
            else:
                print("你可以隨便打幾個字，別讓自己完全消失在這一關。")
                continue
        return ans


def append_note(state: Dict[str, Any], note: str):
    """新增人生小筆記（去除空白與重複）"""
    note = (note or "").strip()
    if note and note not in state["notes"]:
        state["notes"].append(note)


def generate_outcome_text(stage_name: str,
                          context: str,
                          player_choice: str,
                          hp_change: int,
                          tag: str) -> Dict[str, str]:
    """
    統一讓 LLM 幫忙寫：
    - result：這一關的故事結果敘述
    - note：一則人生小筆記（B+C 風格：靠北又是短句金句）

    回傳：
    {
      "result": "...",
      "note": "..."
    }
    """
    system_prompt = (
        "你是一款文字冒險遊戲《亞洲人生存大挑戰》的旁白。\n"
        "你的任務是根據提供的關卡名稱、背景情境、玩家選擇與 HP 變化，"
        "寫出這一關的結果敘述，以及一句「人生小筆記」。\n\n"
        "【結果敘述 result】\n"
        "- 使用繁體中文。\n"
        "- 100～200 字左右，有畫面感，語氣可以微靠北、微自嘲，但要溫柔。\n"
        "- 不要出現技術細節（分數、程式、JSON 等）。\n\n"
        "【人生小筆記 note】\n"
        "- 使用繁體中文。\n"
        "- 風格為 B+C：\n"
        "  * B：有點幽默靠北、帶一點自嘲或吐槽；\n"
        "  * C：短句金句，大約 8～20 字。\n"
        "- 例子（不要重複使用，只當風格參考）：\n"
        "  「不是我不行，是世界太難搞。」\n"
        "  「你不是成績單附屬品。」\n"
        "  「有些沉默是在保護自己。」\n"
        "  「活成別人口中的好孩子，很累。」\n\n"
        "請只輸出 JSON 格式：{\"result\": \"...\", \"note\": \"...\"}"
    )

    user_prompt = f"""
【關卡名稱】
{stage_name}

【背景情境】
{context}

【玩家選擇】
{player_choice}

【HP 變化】
本關 HP 變化：{hp_change}（可能正也可能負）

【評分標籤】
{tag}

請產生符合上述規則的 result 與 note。
"""

    data = call_llm_json(system_prompt, user_prompt, temperature=0.8)
    # 保底處理
    result = str(data.get("result", "")).strip()
    note = str(data.get("note", "")).strip()
    if not note:
        # 若 note 沒給好，再補一句
        backup = call_llm(
            system_prompt=(
                "你是一個人生小筆記產生器，風格為 B+C："
                "有點幽默靠北、又是 8～20 字的短句金句。"
            ),
            user_prompt="請寫一句人生小筆記，使用繁體中文。",
            temperature=0.7,
        )
        note = backup.strip().replace("\n", " ")
        if len(note) > 24:
            note = note[:24]
    return {"result": result, "note": note}


# ======== 各關卡：評分與流程 ========

# --- 第一關：出生 ---

def play_stage_1_birth(state: Dict[str, Any]) -> Dict[str, Any]:
    stage_name = "第一關：出生決定性別"
    print("你還沒看到世界長什麼樣，產房外一群長輩已經在猜你的性別。")
    print("在這個超傳統、設定有點誇張的亞洲家庭裡，性別會直接決定開局難度。\n")

    gender = get_player_input(
        "請選擇你出生的性別（輸入 male / female / other）：",
        state
    ).lower()

    hp_change = 0
    tag = ""
    if gender == "female":
        print("\n產房外瞬間安靜三秒，空氣裡飄著一種說不出口的失落。")
        print("有人說：「唉…女兒也不錯啦……」但語氣一點都沒說服力。\n")
        hp_change = -30
        tag = "female_hard_mode"
        note = "這不是妳的錯，是這片地圖太難。"
    elif gender == "other":
        print("\n你拒絕被性別二分表格限制，系統有點當機，但你成功在世界上留了一個問號。\n")
        hp_change = -20
        tag = "non_binary"
        note = "世界很愛要你勾『男/女』，你可以先勾自己。"
    else:
        print("\n長輩們露出一種「好，至少以後有人可以扛房貸」的表情。")
        print("你安全出生，也背上了一個看不見的『以後要有出息』 Buff。\n")
        hp_change = 0
        tag = "male_default"
        note = "一出生就被預約責任，連選單都沒看見。"

    state["hp"] += hp_change
    if state["hp"] < 0:
        state["hp"] = 0
    append_note(state, note)

    log_entry = {
        "turn": state["turn"],
        "stage": stage_name,
        "choice": gender,
        "hp_change": hp_change,
        "hp_after": state["hp"],
        "note": note,
        "tag": tag,
    }
    state["logs"].append(log_entry)

    print(f"【本關變化】HP 變化：{hp_change} → 目前 HP：{state['hp']}")
    print(f"【人生小筆記】{note}\n")

    if state["hp"] <= 0:
        state["end_flag"] = "lose"

    state["turn"] += 1
    return state


# --- 第二關：大學志願 ---

def classify_major_and_score(major_text: str) -> (int, str):
    """
    依科系關鍵字判定類型與 HP 變化
    回傳 (hp_change, tag)
    """
    text = major_text

    high_keywords = ["醫", "醫學", "牙醫", "藥學", "電機", "資工", "工程", "電資"]
    mid_keywords = ["商", "企管", "管理", "會計", "財金", "金融",
                    "法律", "法學", "經濟"]
    low_keywords = ["美術", "藝術", "設計", "哲學", "社會", "歷史",
                    "音樂", "戲劇", "舞蹈", "體育"]

    tag = "major_other"
    hp_change = -10  # 預設：長輩有點不滿，但還沒到爆炸

    if any(k in text for k in high_keywords):
        hp_change = 10
        tag = "major_high_status"
    elif any(k in text for k in mid_keywords):
        hp_change = 0
        tag = "major_mid"
    elif any(k in text for k in low_keywords):
        hp_change = -20
        tag = "major_low_status"
    else:
        # 沒明確命中，就當冷門或非典型
        hp_change = -10
        tag = "major_other"

    return hp_change, tag


def play_stage_2_major(state: Dict[str, Any]) -> Dict[str, Any]:
    stage_name = "第二關：大學志願"
    print("你來到填大學志願的教室，桌上是那張改不了命運、但會被長輩唸一輩子的志願表。\n")

    context = (
        "老師在前面講「興趣很重要」，但身後的爸媽在說「填這個以後薪水怎麼辦」。"
        "你手上的筆懸在那一格「第一志願」，好像不是在填科系，是在填以後過年被問幾題。"
    )

    print("請用簡短文字描述你想填的科系或領域（例如：醫學系、資工、商管、美術、哲學系...）")
    major_text = get_player_input("你填下的第一志願是：", state)

    hp_change, tag = classify_major_and_score(major_text)
    state["hp"] += hp_change
    if state["hp"] < 0:
        state["hp"] = 0

    outcome = generate_outcome_text(
        stage_name=stage_name,
        context=context,
        player_choice=major_text,
        hp_change=hp_change,
        tag=tag,
    )

    append_note(state, outcome["note"])

    log_entry = {
        "turn": state["turn"],
        "stage": stage_name,
        "choice": major_text,
        "hp_change": hp_change,
        "hp_after": state["hp"],
        "note": outcome["note"],
        "tag": tag,
    }
    state["logs"].append(log_entry)

    print("\n【結果】")
    print(outcome["result"])
    print(f"\n【HP 變化】{hp_change} → 目前 HP：{state['hp']}")
    print(f"【人生小筆記】{outcome['note']}\n")

    if state["hp"] <= 0:
        state["end_flag"] = "lose"

    state["turn"] += 1
    return state


# --- 第三關：第一份工作（固定三選一） ---

def play_stage_3_job(state: Dict[str, Any]) -> Dict[str, Any]:
    stage_name = "第三關：第一份工作"
    print("你畢業了，來到人生第一份工作的十字路口。")
    print("桌上有三封錄取通知，各自通往不同類型的「被比較人生」。\n")

    jobs = [
        {
            "id": "1",
            "title": "連鎖餐飲店基層員工",
            "desc": "工時爆長、輪班制、底薪微薄，但至少不用坐在辦公室。",
            "hp_change": -15,
            "tag": "job_low_status"
        },
        {
            "id": "2",
            "title": "科技業輪班工程師",
            "desc": "薪水漂亮、工時更漂亮，過年回家長輩會誇你，但你不一定還有命回家。",
            "hp_change": 10,
            "tag": "job_high_pay"
        },
        {
            "id": "3",
            "title": "基層公務員",
            "desc": "收入普通、生活穩定，長輩會說「至少有鐵飯碗」，同學會說「你好保守」。",
            "hp_change": 5,
            "tag": "job_stable"
        },
    ]

    print("請從以下三份工作中選擇一個：")
    for job in jobs:
        print(f"{job['id']}. {job['title']}：{job['desc']}")
    print()

    while True:
        choice = get_player_input("請輸入 1 / 2 / 3 選擇你的第一份工作：", state)
        selected = next((j for j in jobs if j["id"] == choice), None)
        if selected:
            break
        print("看起來你選到不存在的工作，再試一次（輸入 1 / 2 / 3）。")

    hp_change = selected["hp_change"]
    tag = selected["tag"]
    state["hp"] += hp_change
    if state["hp"] < 0:
        state["hp"] = 0

    context = "你拿著錄取通知，心裡在算的不只是薪水，還有以後過年被問幾句。"
    outcome = generate_outcome_text(
        stage_name=stage_name,
        context=context,
        player_choice=selected["title"],
        hp_change=hp_change,
        tag=tag,
    )

    append_note(state, outcome["note"])

    log_entry = {
        "turn": state["turn"],
        "stage": stage_name,
        "choice": selected["title"],
        "hp_change": hp_change,
        "hp_after": state["hp"],
        "note": outcome["note"],
        "tag": tag,
    }
    state["logs"].append(log_entry)

    print("\n【結果】")
    print(outcome["result"])
    print(f"\n【HP 變化】{hp_change} → 目前 HP：{state['hp']}")
    print(f"【人生小筆記】{outcome['note']}\n")

    if state["hp"] <= 0:
        state["end_flag"] = "lose"

    state["turn"] += 1
    return state


# --- 第四關：結婚對象（三選一，固定評分） ---

def play_stage_4_marriage(state: Dict[str, Any]) -> Dict[str, Any]:
    stage_name = "第四關：結婚對象"
    print("你的人生來到「長輩開始問婚事」的階段。")
    print("桌上出現三個對象，感覺不是在選伴侶，是在選家族 KPI。\n")

    partners = [
        {
            "id": "1",
            "title": "家世很好但個性不太好的人",
            "desc": "長輩超愛，朋友替你擔心，你自己有點不太確定。",
            "hp_change": 5,
            "tag": "partner_family_approved"
        },
        {
            "id": "2",
            "title": "條件普通但個性很好的人",
            "desc": "你跟他相處很舒服，長輩覺得「還行啦」，沒有特別驚艷。",
            "hp_change": 0,
            "tag": "partner_balanced"
        },
        {
            "id": "3",
            "title": "收入較低但非常契合的靈魂伴侶",
            "desc": "你們互相懂彼此，但長輩覺得這段關係「沒有未來」。",
            "hp_change": -15,
            "tag": "partner_family_disapproved"
        },
    ]

    print("請從以下三位對象中選擇一個：")
    for p in partners:
        print(f"{p['id']}. {p['title']}：{p['desc']}")
    print()

    while True:
        choice = get_player_input("請輸入 1 / 2 / 3 選擇你的結婚對象：", state)
        selected = next((p for p in partners if p["id"] == choice), None)
        if selected:
            break
        print("這個對象目前不在劇情名單裡，再試一次（輸入 1 / 2 / 3）。")

    hp_change = selected["hp_change"]
    tag = selected["tag"]
    state["hp"] += hp_change
    if state["hp"] < 0:
        state["hp"] = 0

    context = "婚禮照片看起來很漂亮，但最難搞的從來不是婚禮，而是兩個家族的期待。"
    outcome = generate_outcome_text(
        stage_name=stage_name,
        context=context,
        player_choice=selected["title"],
        hp_change=hp_change,
        tag=tag,
    )

    append_note(state, outcome["note"])

    log_entry = {
        "turn": state["turn"],
        "stage": stage_name,
        "choice": selected["title"],
        "hp_change": hp_change,
        "hp_after": state["hp"],
        "note": outcome["note"],
        "tag": tag,
    }
    state["logs"].append(log_entry)

    print("\n【結果】")
    print(outcome["result"])
    print(f"\n【HP 變化】{hp_change} → 目前 HP：{state['hp']}")
    print(f"【人生小筆記】{outcome['note']}\n")

    if state["hp"] <= 0:
        state["end_flag"] = "lose"

    state["turn"] += 1
    return state


# --- 第五關：生小孩與否（三選一，固定評分） ---

def play_stage_5_children(state: Dict[str, Any]) -> Dict[str, Any]:
    stage_name = "第五關：生小孩與否"
    print("婚後沒多久，長輩開始問：「什麼時候要抱孫？」")
    print("你面前出現三條路，每一條都會被評論，只是角度不一樣。\n")

    options = [
        {
            "id": "1",
            "title": "生一個小孩",
            "desc": "長輩會說「至少有傳宗接代」，但又會問為什麼不再生一個陪伴。",
            "hp_change": 0,
            "tag": "child_one"
        },
        {
            "id": "2",
            "title": "生兩個小孩",
            "desc": "傳統價值大滿貫：一男一女最好，但你的睡眠品質會被直接清空。",
            "hp_change": 10,
            "tag": "child_two"
        },
        {
            "id": "3",
            "title": "不生小孩",
            "desc": "你選擇把人生拿回一點自主權，長輩則拿出「誰幫你送終」的經典台詞。",
            "hp_change": -25,
            "tag": "child_none"
        },
    ]

    print("請從以下三個選項中選擇：")
    for o in options:
        print(f"{o['id']}. {o['title']}：{o['desc']}")
    print()

    while True:
        choice = get_player_input("請輸入 1 / 2 / 3 選擇你的決定：", state)
        selected = next((o for o in options if o["id"] == choice), None)
        if selected:
            break
        print("目前劇本裡還沒有這種家庭規劃，再試一次（輸入 1 / 2 / 3）。")

    hp_change = selected["hp_change"]
    tag = selected["tag"]
    state["hp"] += hp_change
    if state["hp"] < 0:
        state["hp"] = 0

    context = "你在醫院產房門口、育兒社團、或房間裡的深夜，反覆確認這個選擇。"
    outcome = generate_outcome_text(
        stage_name=stage_name,
        context=context,
        player_choice=selected["title"],
        hp_change=hp_change,
        tag=tag,
    )

    append_note(state, outcome["note"])

    log_entry = {
        "turn": state["turn"],
        "stage": stage_name,
        "choice": selected["title"],
        "hp_change": hp_change,
        "hp_after": state["hp"],
        "note": outcome["note"],
        "tag": tag,
    }
    state["logs"].append(log_entry)

    print("\n【結果】")
    print(outcome["result"])
    print(f"\n【HP 變化】{hp_change} → 目前 HP：{state['hp']}")
    print(f"【人生小筆記】{outcome['note']}\n")

    if state["hp"] <= 0:
        state["end_flag"] = "lose"

    state["turn"] += 1
    return state


# --- 第六關：過年大拷問（AI 出題 + AI 判風格 + 程式硬性評分） ---

def generate_newyear_question() -> Dict[str, Any]:
    """
    由 AI 產生過年長輩拷問題目與難度。
    回傳格式：
    {
      "question": "...",
      "difficulty": "low/medium/high/extreme"
    }
    """
    system_prompt = (
        "你是一個專門負責設計「過年長輩拷問」題目的出題官。\n"
        "請用繁體中文，設計一題典型的過年長輩會問的問題，"
        "主題可以是：收入、房子、婚姻、小孩、升遷等。\n"
        "同時請為這個問題標註難度等級（low/medium/high/extreme），"
        "愈難的題目通常愈容易讓人崩潰，例如：\n"
        "- low：單純關心工作或生活近況\n"
        "- medium：問薪水、房租、考試成績\n"
        "- high：問買房、結婚、生小孩、比較你跟別人\n"
        "- extreme：同時牽涉多重壓力，例如「同齡誰誰誰都已經怎樣了，你呢？」\n"
        "請只輸出 JSON 物件：{\"question\": \"...\", \"difficulty\": \"...\"}"
    )

    user_prompt = "請產生一個過年長輩會問的拷問問題，並標註難度。"
    data = call_llm_json(system_prompt, user_prompt, temperature=0.9)

    question = str(data.get("question", "最近過得怎麼樣？")).strip()
    difficulty = str(data.get("difficulty", "medium")).strip().lower()
    if difficulty not in DIFFICULTY_SCORES:
        difficulty = "medium"

    return {"question": question, "difficulty": difficulty}


def classify_newyear_answer(question: str, answer: str) -> str:
    """
    讓 AI 判斷玩家回答風格：
    回傳 answer_style ∈ {"balanced", "bragging", "too_humble", "defensive", "refuse", "other"}
    """
    system_prompt = (
        "你是一個語氣分析器，專門判斷在華人家庭過年場合中，"
        "晚輩回答長輩拷問時的風格。\n"
        "請根據「問題」與「回答」判斷回答風格：\n"
        "- balanced：不炫耀、不自貶，留有餘地，客氣又不失禮。\n"
        "- bragging：明顯在炫耀、強調自己很厲害、讓人有點不舒服。\n"
        "- too_humble：一直說自己很爛、很糟、過度自貶。\n"
        "- defensive：語氣明顯有防禦、不耐煩、反擊意味。\n"
        "- refuse：明確拒答、打哈哈完全不回應問題本身。\n"
        "- other：無法判斷或不屬於以上類別。\n"
        "請只輸出 JSON：{\"answer_style\": \"balanced/bragging/...\"}"
    )

    user_prompt = f"""
【長輩提問】
{question}

【晚輩回答】
{answer}
"""
    data = call_llm_json(system_prompt, user_prompt, temperature=0.3)
    style = str(data.get("answer_style", "other")).strip().lower()
    if style not in ["balanced", "bragging", "too_humble", "defensive", "refuse", "other"]:
        style = "other"
    return style


def play_stage_6_newyear(state: Dict[str, Any]) -> Dict[str, Any]:
    stage_name = "第六關：過年大拷問"

    print("你拖著有點不足的睡眠與滿滿的伴手禮，回到睽違已久的老家。")
    print("客廳裡坐滿了已經預約好要問你近況的長輩們。\n")

    q = generate_newyear_question()
    question = q["question"]
    difficulty = q["difficulty"]

    print(f"長輩開口了：\n「{question}」\n")
    print("請輸入你打算怎麼回答（記得：不能過度炫耀，也不能太自貶）：")
    answer = get_player_input("你的回答是：", state)

    style = classify_newyear_answer(question, answer)

    # 根據難度與回答風格做硬性評分
    score_table = DIFFICULTY_SCORES[difficulty]
    if style == "balanced":
        hp_change = score_table["correct"]
        tag = f"newyear_balanced_{difficulty}"
    else:
        hp_change = score_table["wrong"]
        tag = f"newyear_{style}_{difficulty}"

    state["hp"] += hp_change
    if state["hp"] < 0:
        state["hp"] = 0

    context = f"過年客廳裡，大家一邊剝橘子，一邊等你回答：「{question}」。"
    outcome = generate_outcome_text(
        stage_name=stage_name,
        context=context,
        player_choice=answer,
        hp_change=hp_change,
        tag=tag,
    )

    append_note(state, outcome["note"])

    log_entry = {
        "turn": state["turn"],
        "stage": stage_name,
        "question": question,
        "answer": answer,
        "difficulty": difficulty,
        "answer_style": style,
        "hp_change": hp_change,
        "hp_after": state["hp"],
        "note": outcome["note"],
        "tag": tag,
    }
    state["logs"].append(log_entry)

    print("\n【結果】")
    print(outcome["result"])
    print(f"\n【難度等級】{difficulty}")
    print(f"【回答風格】{style}")
    print(f"【HP 變化】{hp_change} → 目前 HP：{state['hp']}")
    print(f"【人生小筆記】{outcome['note']}\n")

    if state["hp"] <= 0:
        state["end_flag"] = "lose"

    state["turn"] += 1
    return state


# --- 第七關：親戚稱謂魔王關（AI 出題 + AI 決定難度，程式硬性評分） ---

def generate_kinship_question() -> Dict[str, Any]:
    """
    由 AI 產生一題親戚稱謂問題。
    回傳格式：
    {
      "question": "...",
      "difficulty": "low/medium/high/extreme",
      "answers": ["丈公", "姑婆的公公"]
    }
    """
    system_prompt = (
        "你是一個專門出「華人親戚稱謂」考題的出題官，"
        "要設計給台灣人玩的稱謂魔王關。\n"
        "請用繁體中文，產生一題讓人容易崩潰的親戚稱謂問題，例如：\n"
        "- 「姑婆的公公要怎麼稱呼？」答案：丈公\n"
        "- 「媽媽的阿公的兄弟要怎麼稱呼？」答案：姑丈公\n"
        "請自創一題，並提供：\n"
        "- question：題目文字\n"
        "- difficulty：low/medium/high/extreme（難度愈高，關係愈繞口）\n"
        "- answers：一個或多個可以接受的正確稱呼（字串陣列）\n"
        "請只輸出 JSON 物件，如：\n"
        "{\n"
        "  \"question\": \"姑婆的公公要怎麼稱呼？\",\n"
        "  \"difficulty\": \"high\",\n"
        "  \"answers\": [\"丈公\"]\n"
        "}"
    )

    user_prompt = "請產生一題親戚稱謂魔王題。"
    data = call_llm_json(system_prompt, user_prompt, temperature=0.9)

    question = str(data.get("question", "姑婆的公公要怎麼稱呼？")).strip()
    difficulty = str(data.get("difficulty", "high")).strip().lower()
    answers = data.get("answers", [])
    if not isinstance(answers, list):
        answers = [str(answers)]
    answers = [str(a).strip() for a in answers if str(a).strip()]

    if difficulty not in DIFFICULTY_SCORES:
        difficulty = "high"
    if not answers:
        answers = ["丈公"]

    return {
        "question": question,
        "difficulty": difficulty,
        "answers": answers,
    }


def normalize_kinship_answer(ans: str) -> str:
    """簡單正規化玩家輸入（去空白、全形空格等）。"""
    return ans.replace(" ", "").replace("　", "").strip()


def check_kinship_correct(player_answer: str, answers: List[str]) -> bool:
    norm_player = normalize_kinship_answer(player_answer)
    for a in answers:
        if not a:
            continue
        norm_a = normalize_kinship_answer(a)
        if norm_a and norm_a in norm_player:
            return True
        if norm_player and norm_player in norm_a:
            return True
    return False


def play_stage_7_kinship(state: Dict[str, Any]) -> Dict[str, Any]:
    stage_name = "第七關：親戚稱謂魔王關"

    print("最後一關，你被丟進家族族譜的迷宮。")
    print("長輩決定考你一題「你到底叫人家什麼」的稱謂魔王題。\n")

    q = generate_kinship_question()
    question = q["question"]
    difficulty = q["difficulty"]
    answers = q["answers"]

    print(f"題目來了：\n「{question}」\n")
    player_answer = get_player_input("請輸入你覺得正確的稱呼（例如：丈公、姑丈公...）：", state)

    is_correct = check_kinship_correct(player_answer, answers)
    score_table = DIFFICULTY_SCORES[difficulty]
    if is_correct:
        hp_change = score_table["correct"]
        tag = f"kinship_correct_{difficulty}"
    else:
        hp_change = score_table["wrong"]
        tag = f"kinship_wrong_{difficulty}"

    state["hp"] += hp_change
    if state["hp"] < 0:
        state["hp"] = 0

    context = f"你在一張看不完的家族圖前，試著把「{question}」這題念順。"
    outcome = generate_outcome_text(
        stage_name=stage_name,
        context=context,
        player_choice=player_answer,
        hp_change=hp_change,
        tag=tag,
    )

    append_note(state, outcome["note"])

    log_entry = {
        "turn": state["turn"],
        "stage": stage_name,
        "question": question,
        "player_answer": player_answer,
        "correct_answers": answers,
        "difficulty": difficulty,
        "is_correct": is_correct,
        "hp_change": hp_change,
        "hp_after": state["hp"],
        "note": outcome["note"],
        "tag": tag,
    }
    state["logs"].append(log_entry)

    print("\n【結果】")
    print(outcome["result"])
    print(f"\n【正確答案之一】{answers[0] if answers else '（題庫出問題了…就當你對一半）'}")
    print(f"【你是否答對】{'答對' if is_correct else '答錯'}")
    print(f"【難度等級】{difficulty}")
    print(f"【HP 變化】{hp_change} → 目前 HP：{state['hp']}")
    print(f"【人生小筆記】{outcome['note']}\n")

    if state["hp"] <= 0:
        state["end_flag"] = "lose"

    state["turn"] += 1
    return state


# ======== 最後結局回顧 ========

def generate_review(state: Dict[str, Any]) -> str:
    """
    根據 logs 生成人生回顧，只能回顧實際走過的七關內容。
    """
    turn_limit = len(state["logs"])
    system_prompt = (
        "你是一款遊戲《亞洲人生存大挑戰》的最後結局旁白，"
        "風格像一個很懂亞洲家庭文化的朋友，在宵夜攤邊陪玩家聊天。\n\n"
        "【重要規則】\n"
        "- 你只能根據 logs 裡「實際發生過的事件」來寫回顧。\n"
        "- 絕對禁止提到玩家沒有走到的關卡或人生階段。\n"
        "- 若玩家只活到第 3 關，你就只寫到第 3 關，後面一律不要腦補。\n\n"
        "【輸出要求】\n"
        "- 使用繁體中文，約 400～700 字。\n"
        "- 依序回顧每一關：大致說明那一關發生什麼事、玩家做了什麼選擇、"
        "  當時可能的心情，並自然帶入當關的人生小筆記（note）。\n"
        "- 可以微靠北、微自嘲，但要尊重玩家的努力，不要嘲笑玩家。\n"
        "- 不要提到技術細節（例如：JSON、程式、分數、Log 等）。\n"
        "- 可以溫柔點出：就算沒有完全符合亞洲傳統的期待，"
        "  這些選擇也構成了他自己的版本的人生。\n"
    )

    user_prompt = f"""
【完整遊戲紀錄 logs】
{json.dumps(state['logs'], ensure_ascii=False, indent=2)}

【玩家最終狀態】
- 最後 HP：{state['hp']}
- end_flag：{state.get('end_flag')}
- 實際走到第幾關：{turn_limit}
- 累積的人生小筆記：
{json.dumps(state['notes'], ensure_ascii=False, indent=2)}

請依照上述規則，寫出一篇人生回顧，不要提及任何未出現在 logs 中的事件或關卡。
"""

    review = call_llm(system_prompt, user_prompt, temperature=0.9)
    return review


# ======== 主流程 ========

def main():
    setup_openai()
    ensure_output_dirs()

    print("============================================")
    print("           《亞洲人生存大挑戰》七關版")
    print("============================================\n")

    print("歡迎來到亞洲人生模擬器。")
    print("這次你會經歷七關：")
    print("從出生、選科系、第一份工作、結婚、生不生小孩，")
    print("一路到過年大拷問，以及最終的親戚稱謂魔王關。\n")

    print("【遊戲規則】")
    print(f"- 初始生命值 HP = {INITIAL_HP}。")
    print("- 每一關都會對你丟出一點東西：期待、比較、或靈魂拷問。")
    print("- 程式會用一套固定規則幫你算：這樣選，在亞洲傳統裡會不會被扣血。")
    print("- 每關都會留下至少一則「人生小筆記」。")
    print("- 只要 HP 歸零，無論在第幾關，都直接 Game Over。\n")

    print("【小提示】")
    print("- 任何一關輸入時，只要打：note，就可以隨時翻開人生小筆記小抄。\n")

    state = init_game_state()

    # 關卡依序進行
    while state["turn"] <= MAX_TURNS and state.get("end_flag") is None and state["hp"] > 0:
        print("\n======================================")
        chapter = CHAPTERS[state["turn"] - 1]
        print(f" 第 {state['turn']} 關：{chapter['name']}")
        print("======================================\n")

        if state["turn"] == 1:
            state = play_stage_1_birth(state)
        elif state["turn"] == 2:
            state = play_stage_2_major(state)
        elif state["turn"] == 3:
            state = play_stage_3_job(state)
        elif state["turn"] == 4:
            state = play_stage_4_marriage(state)
        elif state["turn"] == 5:
            state = play_stage_5_children(state)
        elif state["turn"] == 6:
            state = play_stage_6_newyear(state)
        elif state["turn"] == 7:
            state = play_stage_7_kinship(state)
        else:
            break  # 理論上不會到這裡

        if state["hp"] <= 0:
            state["end_flag"] = "lose"
            break

    # 最終勝負判定
    if state["hp"] <= 0:
        state["end_flag"] = "lose"
    elif state.get("end_flag") is None and state["turn"] > MAX_TURNS:
        state["end_flag"] = "win"

    print("\n======================================")
    print("             人生冒險結算")
    print("======================================")

    if state["end_flag"] == "win":
        print("你一路撐過七關，雖然不一定每一題都符合長輩期待，")
        print("但至少，你是用自己的方式撐完這一輪。以亞洲人生來說，這已經是 SSR 結局了。")
    elif state["end_flag"] == "lose":
        print("這一輪，你在某一關被現實或家族文化一拳打趴。")
        print("不過，這片地圖本來就很難破，能撐到這裡已經很不簡單。")
    else:
        print("你停在一個很曖昧的地方：沒有輸得很徹底，也還沒贏。")
        print("某種程度上，這好像才是最多人真實的人生狀態。")

    # 生成人生回顧
    review = generate_review(state)

    review_with_notes = review + "\n\n===== 本輪人生小筆記 =====\n"
    if state["notes"]:
        for idx, note in enumerate(state["notes"], start=1):
            review_with_notes += f"{idx}. {note}\n"
    else:
        review_with_notes += "本輪尚無人生小筆記。\n"

    save_state(state)
    save_summary(review_with_notes)

    print("\n===== 本次《亞洲人生存大挑戰》人生回顧 =====\n")
    print(review_with_notes)

    print("\n謝謝你讓自己認真活過這一輪。如果哪天想重開一輪，我們再來。")




if __name__ == "__main__":
    main()