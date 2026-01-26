# template

Git based project templates.

## Usage

`template -h` `template init -h` `template config -h`

```sh
# uses the default type (by default `raw`)
template init https:/github.com/example/template new_project
# you can manually specify `raw`
template init -t raw https:/github.com/example/template new_project
# -t github is a shorthand for `https://github.com/{}`
template init -t github example/template new_project
# specify a branch/tag/commit with -b
template init -t github example/template new_project -b v0.1.0

# makes a new -t `local`
template config types.local /home/sakh/Documents/Templates/{}
# deletes the type
template config types.local none
# prints config value
template config types.local

# sets default -t to `local`
template config default local
# resets the default
template config default none
# prints config value
template config default
```
