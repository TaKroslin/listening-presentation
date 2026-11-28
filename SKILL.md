---
name: listening-presentation
description: 英语时文听力课件（Listening - Presentation）：把一篇新闻英语文章做成「Latest News」遮挡式听写 PPT——封面 + 听力页（听力词被蓝色块遮住，音频跨页播放）+ 答案页（同版式，点击色块逐个消失）+ 可选视频页。用户给文章（图片/视频可选），直接产出可上课的 16:9 PPTX，含免费男声 TTS 与配图。用于「时文听力 / listening PPT / 听力课件 / 做一篇听力」类请求。
---

# Listening - Presentation

把一篇英语时文做成一份可以直接上课的听力课件。**文章是唯一必填项**；图片缺了由你去找，视频缺了不主动找。做完直接交付 PPTX（音频、配图、动画全部内嵌），不要先给大纲等审批。

## 一、成品结构

| 页 | 内容 |
|---|---|
| 1 | 封面：固定「Latest News」蓝色叠纸版式 + 自拟标题 + 一张新闻图 |
| 2…n+1 | 听力页：文章正文，每页 3–4 句（把页面铺满，别一段一页）；听力词被蓝色块遮住；第 1 页放音频（开始条件＝**单击时**，点喇叭图标播放） |
| n+2…2n+1 | 答案页：与听力页**逐页同版式**，遮罩加「点击消失」退出动画 |
| 最后 | 视频页：全幅内嵌视频（仅当用户提供了视频；没有就不加） |

音频只有一条，嵌在**第一张听力页**，`numSld` 覆盖全部听力页。开始条件设为 **「单击时」**：点击喇叭图标开始播放，一次连续播放到底。

## 二、设计规范（从 `时文听力` 示例提取，已按像素校准）

- 画布 **20 × 11.25 in**（16:9）。深蓝渐变底 + 米白纸张页（`#FFFBF0`，1.4pt 黑边，柔和投影）。
- 正文 **Times New Roman Bold 54pt**（默认 54，按篇幅自动向下缩；3 页方案常见 54/50/50），行距 single，黑色 `#111111`；听力词红色 `#FF0000`；中文释义 0.78×、灰色 `#777066`（仅按需，见下）。
- 遮罩：主题蓝 **`#4F81BD`**，无边框；高度约 `1.06 × 字号`，垂直对准字形。
- 版式：
  - 文本起点 `(0.66, 0.55)`；图片占右侧约 30%（`x 13.35–19.32`，`y 3.45–9.95`）。
  - 开头几行文字**通栏**（宽 18.9in）走在图片上方，之后自动收窄到 12.45in，绕开图片——这是示例的「文字绕图」效果。
  - 图片统一按目标比例居中裁切（近方形 5.95×6.15），加白边 + 细灰线；页面左下角 8pt 灰字放图片署名。
- 封面：「Latest News」用 **Georgia Bold** 118pt 奶油白，压在 `#004AAD` 蓝条上；标题 Times New Roman Bold 54→自动缩字，放在左下；新闻图 6.95×4.63 放右下；照片署名 7pt。
- 音频图标：喇叭 PNG 0.58in，放在第 1 张听力页**右下角**（`18.98, 10.08`），旁边 11pt「LISTEN」。

### 生词规则

- 每页 **5–6 个**，目标是**短语 + 单词混搭**，长度 1–3 词为主（如 `stock market debut`、`at its peak`、`criticism`），不要全是单字，也不要整页都是长短语。
- 只勾高中生该掌握的：听力短语（`in the hands of a few`、`far beyond`）和进阶词（`unsettling`、`restrictive`、`illusion`）；**不要勾专业术语**（valuation、geopolitical、accountability、IPO 这类金融/政治行话）。
- 难度控制在 **B2 左右**，优先高中课本和时事新闻里能见到的词；不要挑生僻词、专有名词、数字。
- 只遮英文词/短语本身，**不要遮标点、中文、句号**。
- 中文释义默认**不进正文**（会破坏换行、且等于给答案）；把「词 + 释义」写进该页**备注（演讲者视图）**，老师看得见、学生看不见。需要给提示时再在 spec 里开 `inline_gloss`。

## 三、工作流

0. **先确认配音（开工前必做）**：用 `ask_user_question`（没有该工具就用一条消息）问清楚两件事，用户确认后再动文章：

   **① 声音**（默认 A）：

   | key | 音色 | 口音 | 特点 |
   |---|---|---|---|
   | A | `en-US-AndrewNeural` 男 | 美音 | 温暖自然，最像真人播客（默认） |
   | B | `en-US-ChristopherNeural` 男 | 美音 | 新闻主播，权威 |
   | C | `en-US-GuyNeural` 男 | 美音 | 情绪饱满 |
   | D | `en-US-BrianNeural` 男 | 美音 | 随和口语 |
   | E | `en-GB-RyanNeural` 男 | 英音 | 友好清晰 |
   | F | `en-GB-ThomasNeural` 男 | 英音 | 标准 RP |
   | G | `en-AU-WilliamMultilingualNeural` 男 | 澳音 | 轻松 |
   | H | `en-CA-LiamNeural` 男 | 加拿大音 | 平和 |
   | I | `en-IN-PrabhatNeural` 男 | 印度音 | 清晰 |
   | J | `en-US-AriaNeural` 女 | 美音 | 新闻，积极 |
   | K | `en-US-JennyNeural` 女 | 美音 | 亲切耐心 |
   | L | `en-US-AvaNeural` 女 | 美音 | 生动 |
   | M | `en-US-EmmaNeural` 女 | 美音 | 明亮口语 |
   | N | `en-GB-SoniaNeural` 女 | 英音 | 端庄 |
   | O | `en-GB-LibbyNeural` 女 | 英音 | 明亮年轻 |
   | P | `en-AU-NatashaNeural` 女 | 澳音 | 友善 |
   | Q | `en-IN-NeerjaNeural` 女 | 印度音 | 清楚 |

   问题只给常用 4–6 个（A/B/E/J/N + 「其他音色见列表」），不要把 17 行全塞给用户。
   **② 语速**：`-8%` 慢 / `-3%` 稍慢 / `+0%` 正常 / `+3%` 稍快（默认）/ `+8%` 快。

   用户已经指定音色或语速时跳过提问。完整列表随时可跑：
   `python scripts/make_audio.py --list-voices`

1. **读文章**，拟一个新闻标题（≤ 70 字符，能压在封面 3 行内）。
2. **分页＝排满**：不要一段一页，按「每一页都排满」来分。250 词左右的文章 ≈ **3 页**，每页 3–4 句 / 70–90 词；**每页文字高度要达到 8.6–9.6in（文本区的 88–98%）**，最后一页也一样，不要留半页空白。文字不够就把下一句挪过来/调大字号；太挤就挪走一句。
3. **选词**：按上面的规则挑 4–5 个/页，记录 English + 中文。
4. **配图**（用户没给时）：Wikimedia Commons API 搜 CC 图，下载后按 5.95×6.15 居中裁切；封面图另按 3:2 裁。来源写进 spec 的 `credit` 与 `cover_credit`。
5. **音频**：按第 0 步用户确认的音色/语速跑 `scripts/make_audio.py`（默认 `en-US-AndrewNeural` / `+3%`），段间 0.8s / 句间 0.45s，最后 loudnorm 到 -16 LUFS。把最终音色/语速写进 `CREDITS.md`，方便复现。
6. **写 spec**（JSON，见 `references/spec.md`），用一条龙脚本生成（先无遮罩，渲染，按红色词实测遮罩，再出片）：
   ```bash
   PYTHON=<带 python-pptx/Pillow/numpy 的 python> \
     scripts/make_deck.sh build/<slug>/deck.json build/<slug>/<标题>.pptx
   ```
   只改文案、不换字体/字号时，也可以直接 `build_deck.py --spec ... --out ...` 用内置近似值。
7. **看 fill 报告并回炉**：`build_deck.py` 会打印每页 `fill%`。任何一页低于 **88%**（日志里带 `too empty`）都要回去挪句子或合并页面，直到全部 ≥88%，再进入校验。

8. **校验**（不可跳过）：
   ```bash
   officecli validate <pptx> --json          # 必须 0 errors
   officecli view <pptx> issues              # 溢出/格式问题
   scripts/render.sh <pptx> /tmp/preview      # 逐页 PNG（自动躲开 officecli 的路径缓存）
   ```
   逐页看图，重点查：遮罩漏红边、遮住标点、文字压图、字被裁、标题换行难看、图片白边。
9. **交付**：PPTX + 独立 MP3 + 图片/音频来源清单。`present` 出去。

## 四、音频

```bash
python scripts/make_audio.py \
  --text build/<slug>/article.txt \
  --out  build/<slug>/audio.mp3 \
  --voice en-US-AndrewNeural --rate=+3% \
  --note "Listen to the news report." --paragraph-gap 0.8
```

- 免费、无需 key（edge-tts 走微软 Edge 在线语音）。需要联网。
- 男声备选：`en-US-ChristopherNeural`（新闻主播感）、`en-GB-RyanNeural`（英音）。
- 依赖：`pip install edge-tts`，且本机有 `ffmpeg/ffprobe`。
- 首次合成若超时，重试一次即可；不要因此改用机械音。

## 五、图片

Wikimedia Commons 搜索 + 下载（`curl`，UA 必填），缩略图用 `thumb.wikimedia.org/.../1920px-...`。优先 CC BY / CC0 / Public Domain，并记录：

```
Photo: <author or source> / <license> (Wikimedia Commons)
```

本机**没有图像生成模型**。用户没给图时只用真实新闻图，不要编造图片说明；找不到合适图就减少图片页，不要塞无关图。

## 五之二、视频（用户给了才做）

用户给了视频链接 / 文件，就在最后加一页全幅视频；没给不主动找。

1. 下载（B 站/YouTube）：`yt-dlp -f "bv*[height<=1080]+ba/b" --merge-output-format mp4 -o video_raw.mp4 "<url>"`。
2. 统一转 **H.264 + AAC**（HEVC 在部分 PowerPoint / Windows 上放不了）：
   `ffmpeg -i video_raw.mp4 -c:v libx264 -crf 20 -pix_fmt yuv420p -c:a aac -b:a 128k -movflags +faststart video.mp4`
3. 视频若自带左右黑边，先量出内容区（多取几帧，左右黑边宽度取一致值），用 `crop=W:H:X:0` 裁掉再转码。
4. 取 3s 处一帧做封面图 `video_poster.jpg`（PowerPoint 的视频占位图）。
5. spec 里写：
   ```json
   "video": "video.mp4",
   "video_aspect": 1.782,
   "video_poster": "video_poster.jpg"
   ```
   `build_deck.py` 会按比例在 18.2×10in 内居中，加深色底 + 细白边，用 `add_movie` 内嵌（不是外链）。

## 六、目录里有什么

```
SKILL.md                 本文件
scripts/build_deck.py    JSON spec → PPTX（封面/绕图排版/遮罩/音频/点击消失）
scripts/make_audio.py    分段 TTS + 静音拼接 + loudnorm
scripts/render.sh        复制到唯一临时名再逐页渲染（绕开 officecli 缓存）
assets/audio-icon.png    示例同款橙色喇叭图标
references/spec.md       spec 全字段、常量、常见坑
```

## 七、答案页动画（必须真的能点）

每个遮罩一个独立 `clickEffect`：`presetID="2" presetClass="exit" presetSubtype="4"`，配 `anim ppt_x/ppt_y` + `style.visibility=hidden`，并在 `p:timing` 末尾写 `p:bldLst/p:bldP`。**同一页内所有 `p:cTn@id` 必须唯一**（根 1、mainSeq 2、效果从 3 起）——id 重复会导致 PowerPoint 整页动画失效，这就是上一版"点了没反应"的原因。生成后用：

```bash
python - <<'PY'
from lxml import etree
ns={"p":"http://schemas.openxmlformats.org/presentationml/2006/main"}
t=etree.parse("ppt/slides/slide5.xml")  # 解压后
ids=t.xpath("//p:timing//p:cTn/@id",namespaces=ns)
print(len(ids), len(set(ids)))          # 必须相等
PY
```

## 八、踩过的坑（别重犯）

- **officecli 渲染有路径缓存**：同一路径重建后再渲染会拿到旧图。必须 `cp` 成新文件名再 `view`，`render.sh` 已处理。
- **别用 PIL 字宽硬算遮罩就完事**：中文字体回退、kerning、行高都跟渲染器有 1–3% 误差，逐词还会左右漂 5px。正式出片一律走 `make_deck.sh`：无遮罩渲染 → 扫红色像素得到每个词的**实测 bbox** → 生成 masks.json → 带 `--masks` 重建。这样遮罩不会露红边、也不会盖住逗号句号。
- **封面「Latest News」不能只写 Constantia**：本机没装该字体会退成无衬线。用 Georgia Bold（已装、Windows/Mac 都有）。
- **逐字设置中文 lang/ea**：否则中文释义会套西文字体，字重和基线都不对。
- **音频必须同时建 MEDIA 与 AUDIO 两条关系**，`p:pic` 里 `a:audioFile r:link` 指 AUDIO，`p14:media r:embed` 指 MEDIA；否则 PowerPoint 里图标是死的。
- **答案页动画是 `presetClass="exit"` + `style.visibility hidden`**，每个遮罩一个 clickEffect；不要把多个遮罩并进同一 par，否则一次点击全消失。
- **20×11.25 是自定义尺寸**，不是 13.333×7.5；忘了设置会全部错位。

## 九、验收清单

- [ ] 封面标题 3 行内、不压图；图片有署名
- [ ] 3 页左右把文章铺满（每页 3–4 句、70–90 词；构建日志每页 fill ≥88%，无 too empty），文字不压图、不溢出纸张
- [ ] 每页 5–7 个词，遮罩完全盖住单词、不盖标点；渲染图里看不到红色
- [ ] 第 1 张听力页有喇叭图标；`ppt/media` 里有 mp3；`numSld` = 听力页数；timing 的 onClick 目标是 `<p:spTgt spid=.../>`（单击时），不是 `sldTgt`
- [ ] 答案页与听力页逐页同版式；每页遮罩数量与听力页一致；点击一次只消失一个（cTn id 唯一 + bldLst 齐全）
- [ ] `officecli validate` 0 errors；`view issues` 只允许「遮罩盖住文字」这一类 overlap（这是设计本身），不能有 overflow / 越界
- [ ] 有视频才加视频页；视频用 `add_movie` 内嵌，不写外链
