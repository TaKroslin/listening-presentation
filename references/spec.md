# deck.json 规格与实现细节

## 1. 最小示例

```json
{
  "title": "Anthropic's Two-Trillion-Dollar Debut Raises Uncomfortable Questions",
  "band_text": "Latest News",
  "cover_image": "img/cover.jpg",
  "cover_credit": "Photo: TechCrunch / CC BY 2.0 (Wikimedia Commons)",
  "audio": "audio.mp3",
  "audio_icon": "<skill>/assets/audio-icon.png",
  "body_size": 54,
  "pages": [
    {
      "text": "The artificial intelligence industry has just witnessed one of its most extraordinary moments. Anthropic, the company behind Claude, made its stock market debut, raising billions of dollars and reaching a valuation of nearly two trillion dollars at its peak.",
      "targets": [
        {"word": "extraordinary", "gloss": "非凡的"},
        {"word": "debut", "gloss": "首次亮相"},
        {"word": "valuation", "gloss": "估值"},
        {"word": "peak", "gloss": "顶峰"}
      ],
      "image": "img/nasdaq.jpg",
      "credit": "Photo: Wikimedia Commons / CC BY 2.0"
    }
  ],
  "video": null
}
```

## 2. 字段

| 字段 | 必填 | 说明 |
|---|---|---|
| `title` | ✓ | 封面标题。程序按 7.95in 宽自动缩字，保证 ≤3.75in 高 |
| `band_text` | | 封面色条文字，默认 `Latest News` |
| `cover_image` | ✓ | 封面图，程序居中裁成 3:2 |
| `cover_credit` | | 封面图署名，7pt 灰字放在图下 |
| `audio` | ✓ | 整篇音频 mp3；嵌在第 1 张听力页 |
| `audio_icon` | ✓ | 喇叭 PNG；用本 skill 的 `assets/audio-icon.png` |
| `body_size` | | 正文字号，默认 54；程序只在放不下时向下缩（3 页方案常见 54/50/50），不会自动放大 |
| `pages[]` | ✓ | 每页一条，顺序即页序 |
| `pages[].text` | ✓ | 该页正文（2–3 句） |
| `pages[].targets[]` | ✓ | `{word, gloss}`；`word` 可以是单词或 2–3 词短语（`stock market debut`），必须是原文中的连续片段，只遮第一次 |
| `pages[].image` | | 右侧配图；缺省则该页只有文字 |
| `pages[].logo` | | `true` 时把图做成深蓝底白字 logo 卡片（适合公司 logo PNG） |
| `pages[].credit` | | 图片署名，8pt 灰字放页面左下 |
| `pages[].inline_gloss` | | `true` 时中文释义进正文（默认 false，仅写进备注） |
| `video` | | mp4 路径；给了才生成最后一页视频页（建议 H.264/AAC） |
| `video_aspect` | | 视频宽高比，如 `1.782`；不填按 16:9 |
| `video_poster` | | 视频封面图 jpg；不填用默认喇叭图 |

相对路径按 **deck.json 所在目录**解析，不用管从哪个目录执行脚本。

## 3. 生成与校验

```bash
# 正式出片（无遮罩渲染 → 实测遮罩 → 成片）
PYTHON=<带 python-pptx/Pillow/numpy 的 python> scripts/make_deck.sh build/<slug>/deck.json build/<slug>/out.pptx

# 只有文案微调、字体字号没变时，可跳过校准：
python scripts/build_deck.py --spec build/<slug>/deck.json --out build/<slug>/out.pptx
officecli validate build/<slug>/out.pptx --json
officecli view build/<slug>/out.pptx issues
scripts/render.sh build/<slug>/out.pptx /tmp/<slug>-preview
```

`render.sh` 会把文件复制成唯一临时名再渲染，因为 officecli 按路径缓存，直接重渲染同一路径会看到旧图。

## 3.1 masks.json

`make_deck.sh` 会先出无遮罩版并逐页渲染，`calibrate_masks.py` 扫描纯红色词块得到实测 bbox，写出：

```json
{"pages": [[{"x": 0.9, "y": 2.1, "w": 2.4, "h": 0.72}, ...], ...]}
```

`build_deck.py --masks masks.json` 直接采用这些盒子（答案页同坐标），不再用 PIL 估算。换字体、字号、行距后必须重新跑 `make_deck.sh`。

## 4. 关键常量（build_deck.py 顶部）

```
SLIDE 20 × 11.25 in
PAPER (0.36, 0.30, 19.28, 10.65) 米白 #FFFBF0
TEXT  (0.66, 0.55)  窄栏宽 12.45  通栏宽 18.90  图片顶 3.45
IMG   x 13.35–19.32  高 6.15  裁切比例 5.95/6.15
LINE_FACTOR 1.164      PowerPoint 单倍行距 ≈ 1.164 em（实测）
遮罩 高 1.06×字号；x 左移 0.03in；宽 +0.02in
```

这些数字是拿 officecli 渲染结果逐像素校准的。换字体、换字号后需要重新校准：

1. `NO_MASKS=1 python scripts/build_deck.py ...` 生成无遮罩版；
2. 渲染该页，取红色像素的 bbox（正文里只有 target 是红色）；
3. 与带遮罩版对比，调 `x-0.03 / w+0.02 / 高 1.06` 三个量，直到：
   - 红色一个像素都不露；
   - 遮罩不盖住后面紧跟的逗号/句号。

## 5. 实现细节

- 文本用**显式换行**（`a:br`）写成，换行由脚本按测量结果决定，渲染器不会二次折行。
- 中文释义与目标词之间不插空格；`run` 上同时设 `a:latin` 和 `a:ea`（宋体），并写 `lang=zh-CN`。
- 遮罩是后加的矩形（在文字之上），答案页复制同一套坐标，再挂退出动画。
- 音频用 `p:pic` + `a:audioFile`，同时建 `RT.MEDIA` / `RT.AUDIO` 两条关系；timing 里 `p:audio` + `p:seq playFrom(0.0)`，`numSld` 设为听力页数。
- 视频用 `shapes.add_movie()`（带 `poster_frame_image`），Python-pptx 会自动补 `p:video` timing；按 `video_aspect` 在 18.2×10in 内等比居中。
- 视频源若是 HEVC，先转 H.264；B 站源常带左右黑边，用 `crop` 裁到内容区。
- 备注：`listening words` 列表自动写入每页 notes，老师可在演讲者视图看到词义。

## 6. 排障

| 现象 | 原因 | 处理 |
|---|---|---|
| 遮罩位置对不上、红字露头 | 字体/字号变了，常量失配 | 按第 4 节重新校准；先查渲染图红色像素 |
| 渲染图和刚改的文件不一致 | officecli 路径缓存 | 用 `render.sh`，或复制成新文件名 |
| 中文释义变成衬线/字重怪 | 只设了 `a:latin` | 设 `a:ea=宋体` + `lang=zh-CN` |
| 封面「Latest News」是无衬线 | 本机无 Constantia | 用 Georgia Bold |
| 音频图标点了没反应 | 缺 MEDIA/AUDIO 关系或 timing | 检查 `slide2.xml.rels` 里两条 mp3 关系、`<p:audio>` 的 spid |
| 一次点击所有遮罩消失 | 多个效果进了同一 par | 每个遮罩独立 `clickEffect` + 独立 `par` |
| 答案页动画没生效 | `p:timing` 位置/结构错 | 用 `presetID="10" presetClass="exit"` + `animEffect fade` + visibility set |
| 文件打开提示修复 | timing/cTn id 重复 | 每个 cTn id 在同一页内唯一；用程序生成，别手抄 |
| 点击后遮罩不消失 | cTn id 重复 / 缺 bldLst / preset 结构不对 | 用 `add_exit_animations()`；检查 per-slide cTn id 唯一且 `p:bldLst` 覆盖所有 spid |
