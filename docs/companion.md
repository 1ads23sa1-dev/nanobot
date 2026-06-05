# Companion — 拟人聊天配置指南

nanobot 的 **Companion 运行时** 面向微信（`weixin`）等 IM 场景，通过人设、情绪、延迟、多气泡、主动消息与 Dream 记忆，让对话更接近真人聊天。

## 快速开始

### 1. 人设与用户画像

编辑 workspace（默认 `~/.nanobot/workspace/`）：

| 文件 | 作用 |
|------|------|
| `SOUL.md` | 小祥的性格、说话样例、禁用句式、闲聊是否用工具 |
| `USER.md` | 你的昵称、称呼、兴趣、近期生活（Dream 会自动补充） |

首次 `nanobot gateway` 会从 bundled 模板复制这些文件。

### 2. 启用聊天向模型预设

加载配置时，若 `gateway.companion.enabled` 为 true，会自动注入名为 `companion` 的模型预设（若尚未存在）。在 `~/.nanobot/config.json` 中激活：

```json
{
  "agents": {
    "defaults": {
      "modelPreset": "companion",
      "timezone": "Asia/Shanghai"
    }
  },
  "modelPresets": {
    "companion": {
      "label": "小祥聊天",
      "model": "anthropic/claude-sonnet-4-5",
      "temperature": 0.85,
      "maxTokens": 1024
    }
  }
}
```

要点：

- **temperature 0.7–0.9**：口语更自然
- **maxTokens 512–1024**：配合多气泡，避免小作文
- 选用 **对话型模型**，不要用纯 coding 模型

完整配置片段见 [`nanobot/config/companion_defaults.py`](../nanobot/config/companion_defaults.py) 中的 `COMPANION_CONFIG_SNIPPET`。

### 3. Gateway 拟人参数

```json
{
  "gateway": {
    "companion": {
      "enabled": true,
      "channel": "weixin",
      "chatId": "<你的 wxid>",
      "sendProbability": 0.12,
      "minIntervalS": 7200,
      "checkIntervalS": 1200,
      "quietHoursStart": "23:00",
      "quietHoursEnd": "08:00",
      "followupEnabled": true,
      "lightweightChat": true,
      "recentChatSkipMinutes": 30,
      "sanitizeReply": true,
      "maxReplyChars": 300
    },
    "messageBurst": {
      "enabled": true,
      "burstProbability": 0.35,
      "stumbleEnabled": true,
      "stumbleProbability": 0.10
    },
    "selectiveDelay": {
      "enabled": true,
      "minDelayS": 2,
      "maxDelayS": 18,
      "longDelayMinS": 60,
      "longDelayMaxS": 120
    },
    "mood": {
      "enabled": true,
      "decayHalfLifeHours": 8
    }
  }
}
```

| 字段 | 说明 |
|------|------|
| `channel` / `chatId` | 主动消息投递目标；不填则回退到最近会话 |
| `sendProbability` | 每次 cron 检查的发送概率（默认 0.12） |
| `minIntervalS` | 两次主动消息最短间隔（默认 2 小时） |
| `recentChatSkipMinutes` | 用户刚聊过则跳过主动 ping（默认 30 分钟） |
| `lightweightChat` | 纯闲聊跳过 tool loop，直接短回复 |
| `sanitizeReply` | 发送前过滤 AI 腔与过长文本 |

### 4. 确认 Dream 在运行

`dream.enabled: true`（默认每 2 小时）。Dream 维护 `SOUL.md`、`USER.md`、`memory/MEMORY.md`，让 bot 记住你的偏好与重要事件。

启动 gateway 时应看到：

```
✓ Dream: every 2h
```

以及 companion / companion_followup cron 注册。

## 运行时能力（微信）

```text
用户消息 → 正在输入 → Mood 更新 → selective_delay → LLM
         → sanitize → message_burst（分气泡 + stumble）→ 发送
```

- **Mood**：warmth / worry / energy / prickly，影响语气提示与延迟
- **selective_delay**：对「嗯/好的」等低 stakes 消息随机长延迟
- **message_burst**：按 `---` 或句界分多条；偶发「嗯…」犹豫或改口
- **followup**：你沉默后 AI 决定是否再 ping 一句
- **companion cron**：白天随机主动关心（安静时段不打扰）

## 调参建议

| 现象 | 调整 |
|------|------|
| 太话痨 / 主动太勤 | 降低 `sendProbability`，提高 `minIntervalS` |
| 太冷 / 回复太快 | 提高 `selectiveDelay` 的 `maxDelayS`；检查 temperature |
| 像客服 | 确认 `lightweightChat: true`；完善 `SOUL.md` 禁用句式 |
| 回复太长 | 降低 `maxTokens`；启用 `sanitizeReply`；调低 `maxReplyChars` |
| 刚聊完又主动 ping | 提高 `recentChatSkipMinutes` |

## 减少「工具人」倾向

- 在 `SOUL.md` 写明：纯闲聊禁止调工具
- `agents.defaults.disabledSkills`：禁用与聊天无关的 skill
- `tools.restrictToWorkspace: true`

## 验收清单

1. 对「嗯」「好的」，部分回复有 1–3 分钟延迟 + 短句
2. 约 30% 回复拆成 2 条，偶发犹豫/改口
3. 白天随机 1–3 句主动消息，不提 cron/AI
4. 隔日能自然提到 USER/MEMORY 中的事实
5. 样本中「作为 AI/我可以帮你」类句式极少
