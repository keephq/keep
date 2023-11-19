
export default function handler(req, res) {
    res.status(200).json({
        AUTH_TYPE: process.env.AUTH_TYPE,
    });
  }
