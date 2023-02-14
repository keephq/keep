---
sidebar_label: Auto Completion
sidebar_position: 4
---

# 👨🏻‍💻 Auto Completion

<h4>Keep's CLI supports shell auto-completion, which can make your life a lot more easier 😌</h4>

If you're using zsh, add this to `~/.zshrc`
```shell
eval "$(_KEEP_COMPLETE=zsh_source keep)"
```


If you're using bash, add this to `~/.bashrc`
```bash
eval "$(_KEEP_COMPLETE=bash_source keep)"
```


> Using eval means that the command is invoked and evaluated every time a shell is started, which can delay shell responsiveness. To speed it up, write the generated script to a file, then source that.
