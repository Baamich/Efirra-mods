# Sielo mods

The list of mods for [Sielo](https://github.com/Baamich/Sielo-releases), an app for live streams.
The app shows them under the **Mods** button. Русский текст ниже.

A mod is a Lua script or a language. Scripts run in a sandbox: no files, no network, no stream key, and only after the person agrees. Other code is not accepted: no DLL, EXE, VST or web pages.

## Add your mod

Send a pull request that adds one folder for you and one folder per mod:

```
mods/
  your-name/
    developer.json
    your-mod/
      mod.json
      main.lua        a script, or main.json for a language
      README.md       optional
      LICENSE         optional
```

Folder names: lowercase `a-z`, `0-9` and `-`, starting with a letter. `your-name` is shown in the app as the developer, up to 19 characters; `your-mod` up to 20.

`developer.json`:

```json
{ "github": "your-github-login" }
```

`mod.json`:

```json
{
  "kind": "script",
  "name": "Scene timer",
  "version": "1.0",
  "license": "MIT",
  "description": { "en": "Switches scenes on a timer", "ru": "Меняет сцены по таймеру" }
}
```

A language also has `"code": "de"`. Raise `version` whenever the file changes.

The `check` job tells you what to fix. Once it passes, your pull request is merged by itself and the mod appears in the app a few minutes later. Only you can change your folder afterwards: it is tied to your GitHub login. Nobody reads mods before they appear, so a report is how a bad one gets removed.

## Rules

- Your own work, or work you may share, with a license stated.
- No piracy, no adult content, no malware, nothing against the law, no logos you have no right to use.
- A script does what its description says.

Breaking these gets a mod removed and the login blocked. Mods belong to their authors, and each has its own license.

## Report a mod

[Open an issue](https://github.com/Baamich/Sielo-mods/issues/new/choose) and name the mod and the problem.

---

# Моды Sielo

Список модов для [Sielo](https://github.com/Baamich/Sielo-releases), программы для эфиров. В программе они открываются кнопкой **Моды**.

Мод — это скрипт Lua или язык. Скрипт работает в песочнице: без файлов, сети и ключа эфира, и только после согласия человека. Другой код не принимаем: никаких DLL, EXE, VST и веб-страниц.

## Как добавить мод

Пришлите pull request с папкой на себя и папкой на каждый мод (схема и примеры файлов выше). Имена папок: строчные `a-z`, `0-9` и `-`, первой идёт буква. `your-name` показывается в программе как разработчик, до 19 символов; `your-mod` до 20.

В `developer.json` только ваш логин GitHub. При изменении файла поднимайте `version`. Проверка `check` подскажет, что исправить. Когда она пройдена, заявка принимается сама и мод появляется в программе через несколько минут. Менять папку потом сможете только вы: она привязана к вашему логину GitHub. Заранее моды никто не читает, поэтому плохой мод убирается по жалобе.

## Правила

- Своя работа или та, которой можно делиться, с указанной лицензией.
- Без пиратства, контента для взрослых, вредоносного кода, нарушений закона и чужих логотипов без права на них.
- Скрипт делает то, что написано в описании.

За нарушение мод убирается из списка, а логин блокируется. Моды принадлежат авторам, у каждого своя лицензия.

## Пожаловаться на мод

[Создайте issue](https://github.com/Baamich/Sielo-mods/issues/new/choose): какой мод и в чём проблема.
