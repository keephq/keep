---
sidebar_label: ngrok
sidebar_position: 2
---

# 🔗 ngrok

## ngrok?

Imagine you have a secret hideout in your backyard, but you don't want anyone to know where it is. So, you build a tunnel from your hideout to a tree in your friend's backyard. This way, you can go into the tunnel in your yard and magically come out at the tree in your friend's yard.

Now, let's say you have a cool website or a game that you want to show your friend, but it's running on your computer at home. Your friend is far away and can't come to your house. So, you need a way to show them your website or game over the internet.

This is where ngrok comes in! Ngrok is like a magical tunnel, just like the one you built in your backyard. It creates a secure connection between your computer and the internet. It gives your computer a special address that people can use to reach your website or game, even though it's on your computer at home.

When you start ngrok, it opens up a tunnel between your computer and the internet. It assigns a special address to your computer, like a secret door to your website or game. When your friend enters that address in their web browser, it's as if they're walking through the tunnel and reaching your website or game on your computer.

So, ngrok is like a magical tunnel that helps you share your website or game with others over the internet, just like the secret tunnel you built to reach your friend's backyard!

## How to start Keep with ngrok

ngrok is Controlled with the `USE_NGROK` environment variable.<br />
Simply run Keep's API using the following command to start with ngrok: `USE_NGROK=true keep api`

:::note
`USE_NGROK` is enabled by default when running with `docker-compose`
:::

## How to obtain ngrok URL

When `USE_NGROK` is set, Keep will start with ngrok in the background. <br />
You can find your private ngrok URL looking for this log line "`ngrok tunnel`":
```json
{
    "asctime": "0000-00-00 00:00:00,000",
    "message": "ngrok tunnel: https://fab5-213-57-123-130.ngrok.io",
    ...
}
```
The URL (https://fab5-213-57-123-130.ngrok.io in the example above) is a publicly accessible URL to your Keep API service running locally. <br />
:::note
You can check that the ngrok tunnel is working properly by sending a simple HTTP GET request to `/healthcheck`<br />
Try: `curl -v https://fab5-213-57-123-130.ngrok.io/healthcheck` in our example.
:::
