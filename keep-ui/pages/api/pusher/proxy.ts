// pages/api/pusher/proxy.ts
import { NextApiRequest, NextApiResponse } from "next";
import { createServer, IncomingMessage, ServerResponse } from "http";
import { parse } from "url";
import { WebSocketServer, WebSocket } from "ws";
import httpProxy from "http-proxy";

const pusherHost =
  process.env.PUSHER_HOST || `ws-${process.env.PUSHER_CLUSTER}.pusher.com`;
const pusherPort = process.env.PUSHER_PORT
  ? parseInt(process.env.PUSHER_PORT)
  : 443;
const pusherProtocol = process.env.PUSHER_PORT ? "ws:" : "wss:";

const proxy = httpProxy.createProxyServer({
  target: {
    protocol: pusherProtocol,
    host: pusherHost,
    port: pusherPort,
  },
  ws: true,
  changeOrigin: true,
});

const wsServer = new WebSocketServer({ noServer: true });

const handler = (req: NextApiRequest, res: NextApiResponse) => {
  if (req.method === "GET") {
    res.status(200).json({ message: "WebSocket proxy server" });
  } else {
    res.status(405).json({ message: "Method not allowed" });
  }
};

export const config = {
  api: {
    bodyParser: false,
  },
};

if (!(process as any).wss) {
  (process as any).wss = createServer(
    (req: IncomingMessage, res: ServerResponse) => {
      const parsedUrl = parse(req.url!, true);
      if (parsedUrl.pathname === "/api/pusher/proxy") {
        handler(req as NextApiRequest, res as NextApiResponse);
      } else {
        res.writeHead(404).end();
      }
    }
  );

  (process as any).wss.on(
    "upgrade",
    (request: IncomingMessage, socket: any, head: Buffer) => {
      const { pathname } = parse(request.url || "");

      if (pathname === "/api/pusher/proxy") {
        wsServer.handleUpgrade(request, socket, head, (ws: WebSocket) => {
          proxy.ws(request, socket, head);
        });
      } else {
        socket.destroy();
      }
    }
  );

  (process as any).wss.listen(parseInt(process.env.PORT || "3000"));
}

export default handler;
