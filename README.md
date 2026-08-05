# Crom MCP Server

Crom MCP Server 通过 [Model Context Protocol](https://modelcontextprotocol.io/) 查询 Crom API v2。

## 安装依赖

```bash
pip install -r requirements.txt
```

## 以 stdio 方式运行

默认保持 stdio 传输，兼容 Claude Desktop、Cursor 等本地 MCP 客户端：

```bash
python server.py
```

## 以 Streamable HTTP 方式运行

```bash
python server.py --transport streamable-http --host 127.0.0.1 --port 8000
```

启动后端点默认为：

```text
http://127.0.0.1:8000/mcp
```

在容器或远程部署时可监听所有网卡：

```bash
python server.py --transport streamable-http --host 0.0.0.0 --port 8000
```

当 `--host` 不是 `127.0.0.1/localhost/::1` 时，服务会自动关闭 MCP SDK 的
DNS rebinding Host 头校验，允许 AstrBot 等容器或远程客户端通过实际地址访问。
