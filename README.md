# Telefly III - A Telegram bot for Firefly III

## About

This is a [Telegram][] bot for [Firefly III][], which you can use to
submit your expenses on the go. The idea was heavily inspired by
[Firefly Bot by Valmik][vjFaLk/firefly-bot], however I needed a bit more
flexible version. You start entering a transaction by sending an amount
and a description (e.g., `5 Coffee with friends`). Afterwards, **Telefly
III** will ask you about the destination account, category, and budget.
These will be fetched from your Firefly III installation and presented
as a list of buttons. In case of destination account and category, you
can either select an option from the list, or you can type your answer
directly. If there's no such account or category, it will be created
automatically. As for the budget, you can only select the one from the
list. There's also an option not to specify category or budget by
selecting *(none)*.


## Installing and running

There are two options for running **Telefly III**:
[locally](#installing-and-running-locally) or by
[using Docker](#running-using-docker). In both cases you'll have to
install Python 3 and [Python Poetry][].


### Installing and running locally

To install **Telefly III** locally, checkout the repository or download
a release archive and unpack it somewhere. Now you have to create a
configuration file and provide Telegram bot token there. See
[Configuration](#configuration) section for more details.

You have two options to run **Telefly III** locally:
[using Poetry shell](#running-using-poetry-shell) or
[directly from the command line](#running-from-the-command-line).


#### Running using the Poetry shell

First you need to instruct Poetry to create a virtual environment and
install all necessary dependencies. Run the following command inside the
`telefly-iii` folder:

```bash
poetry install --no-dev
```

Afterwards, use the following commands to run the bot:

```bash
poetry run python -m telefly_iii
```

Or, alternatively:

```bash
poetry shell
python -m telefly_iii
```

To stop the bot, use *Ctrl+C*.


#### Running using the command line

First you need to export the dependencies using Poetry and install them
locally using pip. For this, run the following commands inside the
`telefly-iii` folder:

```bash
poetry export -f requirements.txt > requirements.txt
pip install -r requirements.txt
```

Afterwards, use the following commands to run the bot:

```bash
python -m telefly_iii
```

To stop the bot, use *Ctrl+C*.


### Running using Docker

To run **Telefly III** using Docker you need to export the dependencies
using Poetry first:

```bash
poetry export -f requirements.txt > requirements.txt
```

After that, use the included `Dockerfile` to generate a Docker image:

```bash
docker build --tag telefly-iii .
```

When Docker finishes generating an image, you can start **Telefly III**
by executing:

```bash
docker run --detach --name=telefly-iii -v ./config:/config telefly-iii
```

Be sure to update the `./config` part if you store your configuration
somewhere else.

To stop the **Telefly III** container, use:

```bash
docker stop telefly-iii
```

And to start it again, use:

```bash
docker start telefly-iii
```

If you want to update an existing installation, you need to stop the
container, remove it using `docker rm telefly-iii`, and then run `docker
build [...]` and `docker run [...]` steps again. Don't worry, `docker rm
[...]` won't delete your configuration or persistence data. This data is
stored under the path that you specified in the `docker run [...]`
command and is simply mounted into the container.


## Configuration

To be able to run **Telefly III**, you need to have a Telegram bot
token. Check the [official documentation][BotFather Docs] on how to get
one from [BotFather][]. And don't worry, it's free.

When you get your token, put it inside `telefly-iii.ini` file inside the
`config` folder. It should look like this:

```ini
[Bot]
token=<your-token-here>
```

There are few more options you can configure. They are described in
`telefly-iii.ini.default` file. Feel free to use it as a reference.

By default, **Telefly III** will try to load config from the
`config/telefly-iii.ini` file. However, you can also store it under a
different name or even in a different folder. If you do this, you have
to define `TELEFLY_III_CONFIG` environment variable before starting
**Telefly III** and specify a path to config file there. E.g.:

```bash
export TELEFLY_III_CONFIG_FILE=/etc/telefly-iii/config.ini
python -m telefly_iii
```


[Telegram]: https://telegram.org/
[Firefly III]: https://www.firefly-iii.org/
[vjFaLk/firefly-bot]: https://github.com/vjFaLk/firefly-bot
[Docker]: https://www.docker.com/
[Python Poetry]: https://python-poetry.org/
[BotFather Docs]: https://core.telegram.org/bots#6-botfather
[BotFather]: https://t.me/botfather
