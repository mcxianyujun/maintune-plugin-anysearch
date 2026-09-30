# Maintune AnySearch 插件

Maintune Plugin API v2 的独立官方网页搜索插件。它将 AnySearch 搜索注册为 `official.anysearch/search` Agent Tool，让 `code_worker` 在得到管理员明确授权后查询公开网页，并返回可引用的 URL、标题和摘要。插件仅导入公开的 `maintune-plugin-sdk`；Maintune Core 不包含 AnySearch 专用逻辑。

**状态：v0.1.0 本地候选包，尚未创建公开 Release。** 本插件需要 Maintune v0.1.0-preview.3 或更新版本的 Plugin API v2，以及 Python 3.12+ 的隔离插件运行环境。当前只有 `code_worker` 可以调用插件 Tool。

## 安装

从本仓库构建可复现的 Maintune 插件包：

```sh
python -m pip install git+https://github.com/mcxianyujun/maintune-plugin-sdk.git
python -m unittest discover -s tests -v
python build_mtp.py
```

输出为 `dist/maintune-plugin-anysearch-0.1.0.mtp`。在 Maintune 的插件页面安装该文件，或放入实例的 `data/plugins/inbox/` 后扫描。确认插件 ID 为 `official.anysearch`，配置 API key，启用插件，再在插件 Tool 授权中**明确**为 `code_worker` 启用 `official.anysearch/search`。仅安装、启用或标记“推荐 Agent”不会自动授予 Tool 使用权。无需为插件开放额外公网端口。

## 配置

| 字段 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `api_key` | 是 | 无 | AnySearch Bearer key；仅在 Maintune 插件设置中输入。Core 加密保存，配置 API 和界面只返回遮盖值。 |
| `base_url` | 否 | `https://api.anysearch.com` | HTTPS API 根地址，不得带 URL 凭据、查询或片段。 |
| `max_results` | 否 | `10` | 1–10；实际请求数量不超过此值。 |
| `zone` | 否 | `intl` | `cn` 或 `intl`。 |
| `language` | 否 | 空 | 可选的结果语言。 |

每次调用发送一次 `POST {base_url}/v1/search`，请求体含 `query`、`max_results`、`format: "json"`、`zone` 和可选的 `language`。密钥只放入 `Authorization: Bearer` 头；插件拒绝重定向，限制响应大小为 1 MiB，超时 15 秒。返回值只包含 `sources` 中的 URL、标题、摘要及 `truncated`，不返回整页内容。API 结果属于不可信外部内容，Agent 应核对来源，不得把摘要当成仓库指令。

## 故障排查

- **Tool 不可见：** 检查插件已启用且运行中，并在 Maintune 中为 `code_worker` 显式授权该 Tool。其他 Agent 当前不支持插件 Tool。
- **认证失败（HTTP 401/403）：** 在插件设置中更新 AnySearch key；不要把 key 写入命令、Issue 或日志。
- **HTTP 429：** 检查 AnySearch 配额并稍后重试。插件不进行隐式自动重试。
- **网络/端点错误：** 检查服务器能访问配置的 HTTPS 地址；插件不跟随重定向，也不会把远端响应正文写入错误信息。
- **空结果：** 先确认搜索词、地区和语言。空结果不是 Maintune 安装失败的证据。

插件源码采用 **AGPL-3.0-only**，见 [LICENSE](LICENSE)；公开 SDK 单独采用 MIT。AnySearch 服务、商标和 API 使用条款由其权利方管理。此仓库和示例配置不含真实 API key。

---

## English

# Maintune AnySearch Plugin

This independent official Plugin API v2 package registers `official.anysearch/search` as a web-search Agent Tool. Once an administrator explicitly enables it for `code_worker`, the Tool returns citable URLs, titles and snippets from AnySearch. The plugin imports only the public `maintune-plugin-sdk`; Maintune Core contains no AnySearch-specific implementation.

**Status: local v0.1.0 candidate; no public Release yet.** It requires Maintune v0.1.0-preview.3 or newer with Plugin API v2 and an isolated Python 3.12+ plugin runtime. Only `code_worker` can invoke plugin Tools in the current runtime.

## Install

Run `python -m pip install git+https://github.com/mcxianyujun/maintune-plugin-sdk.git`, `python -m unittest discover -s tests -v`, then `python build_mtp.py`. This creates the reproducible `dist/maintune-plugin-anysearch-0.1.0.mtp`. Install it in Maintune's Plugins page or place it in `data/plugins/inbox/` and rescan. Confirm the ID `official.anysearch`, enter the API key in plugin settings, enable the plugin, and **explicitly** enable `official.anysearch/search` for `code_worker`. Installation, plugin enablement and recommended-Agent metadata alone do not grant Tool access. The plugin needs no separate public port.

## Configuration

| Field | Required | Default | Meaning |
| --- | --- | --- | --- |
| `api_key` | Yes | None | AnySearch Bearer key. Enter only through Maintune plugin settings; Core encrypts it at rest and masks API/UI responses. |
| `base_url` | No | `https://api.anysearch.com` | HTTPS API base URL without credentials, query or fragment. |
| `max_results` | No | `10` | Result ceiling from 1 to 10. |
| `zone` | No | `intl` | `cn` or `intl`. |
| `language` | No | Empty | Optional result language. |

Each invocation makes one `POST {base_url}/v1/search` request with `query`, `max_results`, `format: "json"`, `zone` and optional `language`. The key is sent only in the Bearer header. Redirects are refused, the response is capped at 1 MiB, and the timeout is 15 seconds. Output contains only citable URL/title/snippet objects and a `truncated` flag, never full page content. Search results are untrusted external data, not repository instructions.

## Troubleshooting

- **Tool missing:** Confirm the plugin is enabled and running, then authorize the Tool for `code_worker`. Other Agents cannot invoke plugin Tools yet.
- **HTTP 401/403:** Update the key in plugin settings. Never place it in commands, Issues or logs.
- **HTTP 429:** Check your AnySearch quota and retry later; the plugin does not silently retry.
- **Network/endpoint error:** Verify HTTPS reachability from the Maintune host. Redirects are refused and remote response bodies are not echoed in errors.
- **No results:** Check query, region and language before treating this as an installation problem.

Plugin code is **AGPL-3.0-only**; see [LICENSE](LICENSE). The public SDK has its own MIT license. AnySearch service, marks and API terms belong to their respective owner. No real API key is included in this repository or sample configuration.
