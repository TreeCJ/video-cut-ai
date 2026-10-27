# Glossary

## Transcript

一次语音识别（ASR）的完整结果，属于一个视频。包含句子列表和词列表，每条都带时间戳（秒）。落盘为 `transcript.json`，是后续所有时间判断的唯一事实来源。

## Word

转录中的最小单位：一个字/词及其 `begin_time`、`end_time`。来自 ASR 的词级时间戳，用于把文本位置映射回时间点。

## Sentence

转录中的句子：一段连续口播文本及其 `begin_time`、`end_time`。切片边界对齐以 Sentence 为单位。

## Highlight

LLM 从 Transcript 中挑出的一个高光片段：标题、理由、原文引用（quote）、起止时间（start/end,秒）。落盘为 `highlights.json`，可人工修改后再切片。

一组 Highlight 按时间顺序构成一条叙事序列：拼接后观众不看原片也能顺着情节看懂整个视频，而不是互不相干的精彩瞬间集合。序列的总时长受 Merged 时长预算约束（默认 300 秒）。

## Quote

Highlight 中引用的 Transcript 原文句子。作为校验锚：当 Highlight 的 start/end 与 Quote 在 Transcript 中的实际时间偏差超过阈值时，以 Transcript 定位为准。

## Draft

Highlight 序列的人工调整工作副本：用户在 web 界面上改边界、删除、重排后的结果。落盘为 `highlights.draft.json`，与 LLM 产出的原始 `highlights.json` 分离——原始产物永不被修改。存在 Draft 时，切片以 Draft 为准。

## Locked

Highlight 的一种状态：用户在 web 界面上手动改过 start/end 后，该 Highlight 被锁定。锁定的 Highlight 在切片时跳过 Quote 对齐，直接使用人工给定的时间——人工拍板优先于自动锚定。未被锁定的 Highlight 仍走 Quote 对齐。

## Clip

一个 Highlight 切片后的产物：一个独立的 mp4 文件。命名 `<序号>-<标题>.mp4`，放在 `clips/` 下。

## Merged

所有 Clip 按顺序拼接成的单个合集文件 `merged.mp4`。拼接不重编码（stream copy）。

## Segment

切片过程中的中间文件：一个 Clip 在未合并前的独立编码产物，编码参数（帧率、分辨率、码率、声道）全部统一，保证 Merged 可以 stream copy 拼接。

## Provider

LLM 供应商抽象。默认实现为阿里云通义千问（DashScope）。负责"读 Transcript 挑 Highlight"这一步。

## Engine

ASR 引擎抽象。默认实现为阿里云 Paraformer（DashScope 录音文件识别）。负责"音频 → Transcript"这一步。
