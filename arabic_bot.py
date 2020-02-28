import discord
from discord.message import Message
from discord.channel import CategoryChannel, TextChannel, VoiceChannel, DMChannel
from discord.guild import Guild
from discord.member import Member

import time

import os
import asyncio
import random
import requests

import sqlite3
import ast

import tracemalloc
import logging

import conf;

scriptName = str(os.path.basename(__file__).split(".")[0])
print("Starting", scriptName)

tracemalloc.start()
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.WARN)
logger = logging.getLogger(__name__)

dbConnection = sqlite3.connect(f"data_{scriptName}.db", isolation_level=None, check_same_thread=False)

# noinspection PyTypeChecker
targetChannelInDiscord: TextChannel = None

arabic = list('؀؁؂؃؋،؍؎؏ؐؑؒؓؔؕ؛؞؟ءآأؤإئابةتثجحخدذرزسشصض'
              'طظعغـفقكلمنهوىيًٌٍَُٞ٠١٢٣٤٥٦٧٨٩٪٫٬'
              '٭ٮٯٰٱٲٳٴٵٶٷٸٹٺٻټٽپٿڀځڂڃڄڅچڇڈډڊڋڌڍڎڏڐڑڒړڔ'
              'ڕږڗژڙښڛڜڝڞڟڠڡڢڣڤڥڦڧڨکڪګڬڭڮگڰ'
              'ڱڲڳڴڵڶڷڸڹںڻڼڽھڿۀہۂۃۄۅۆۇۈۉۊۋیۍێۏېۑے'
              'ۓ۔ەۖۗۘۙۚۛۜ۝۞ۣ۟۠ۡۢۤۥۦۧۨ۩۪ۭ۫۬ۮۯ۰۱۲۳۴۵۶۷۸۹ۺۻۼ۽۾ۿ'
              'ﺎﺍﺐﺒﺑﺏﺖﺘﺗﺕﺚﺜﺛﺙﺞﺠﺟﺝﺢﺤﺣﺡﺦﺨﺧ'
              'ﺥﺪﺩﺬﺫﺮﺭﺰﺯﺲﺴﺳﺱﺶﺸﺷﺵﺺﺼﺻﺹﺾ'
              'ﻀﺿﺽﻂﻄﻃﻁﻆﻈﻇﻅﻊﻌﻋﻉﻎﻐﻏﻍﻒ'
              'ﻔﻓﻑﻖﻘﻗﻕﻚﻜﻛﻙﻞﻠﻟﻝﻢﻤﻣﻡﻦﻨﻧﻥﻪﻬﻫﻩﻮﻭﻲﻴﻳﻱ')

currentId = -1


async def readOneSQL(sql, *args):
    data = await loop.run_in_executor(None, lambda: dbConnection.cursor().execute(sql, args).fetchone())
    return data


async def readAllSQL(sql, *args):
    data = await loop.run_in_executor(None, lambda: dbConnection.cursor().execute(sql, args).fetchall())
    return data


async def execSQL(sql, *args):
    return await loop.run_in_executor(None, lambda: dbConnection.cursor().execute(sql, args))


class botSettings:
    def __init__(self, indDbId, ownerId, targetChannel, currentQuestion, payload, value, interval, admins):
        self.indDbId: int = indDbId
        self.ownerId: int = ownerId
        self.targetChannel: int = targetChannel
        self.currentQuestion: int = currentQuestion
        self.payload: str = str(payload)
        self.value: dict = ast.literal_eval(value)
        self.interval: int = interval
        self.admins: list = ast.literal_eval(admins)

    async def pushChanges(self):
        await execSQL(
            "UPDATE arabicbot_settings SET `ownerId` = ?, `targetChannel` = ?,"
            " `currentQuestion` = ?, `payload` = ?, `value` = ?, interval = ?, admins = ?  WHERE indDbId = ?",
            self.ownerId, self.targetChannel, self.currentQuestion, self.payload, str(self.value), self.interval,
            str(self.admins), self.indDbId)

async def getSettings(inDbId: int = 1):
    res = await readOneSQL("SELECT * FROM arabicbot_settings WHERE indDbId = ?", inDbId)
    if res is None:
        return None
    else:
        return botSettings(*res)


class botUser:
    def __init__(self, userId, score, participatedIn, name):
        self.userId: int = userId
        self.score: int = int(score)
        self.participatedIn: list = ast.literal_eval(participatedIn)
        self.name: str = str(name)

    async def pushChanges(self):
        await execSQL("UPDATE arabicbot_user SET `score` = ?, `participatedIn` = ?, `name` = ? WHERE userId = ?",
                      float(self.score), str(self.participatedIn), self.name, self.userId)


async def getUser(inDbId: int):
    res = await readOneSQL("SELECT * FROM arabicbot_user WHERE userId = ?", inDbId)
    if res is None:
        return None
    else:
        return botUser(*res)


class botQuestion:
    def __init__(self, inDbId, score, question, answer):
        self.inDbId: int = inDbId
        self.score: int = int(score)
        self.question: str = str(question)
        self.answer: str = str(answer)

    async def pushChanges(self):
        await execSQL("UPDATE arabicbot_question SET `score` = ?, `question` = ?, `answer` = ? WHERE inDbId = ?",
                      float(self.score), self.question, self.answer, self.inDbId)


async def getQuestion(inDbId: int):
    res = await readOneSQL("SELECT * FROM arabicbot_question WHERE inDbId = ?", inDbId)
    if res is None:
        return None
    else:
        return botQuestion(*res)


class MyClient(discord.Client):
    async def on_ready(self):
        global targetChannelInDiscord
        settings = await getSettings()
        for channel in self.get_all_channels():
            channel: TextChannel
            if channel.id == settings.targetChannel:
                targetChannelInDiscord = channel
                break
        if targetChannelInDiscord:
            print('Found target channel', targetChannelInDiscord)
            await targetChannelInDiscord.send("Hi, the bot is activated!")
        print('Logged on as {0}'.format(self.user))

    async def on_message(self, message: Message):
        global targetChannelInDiscord
        sender: Member = message.author
        channel = message.channel
        if sender.id == self.user.id:
            return
        settings = await getSettings()
        if message.channel == targetChannelInDiscord:
            # await message.add_reaction('\N{TIMER CLOCK}')
            currentUser = await getUser(sender.id)
            if not currentUser:
                await execSQL("insert into arabicbot_user (userId, name) "
                              "VALUES (?, ?)", sender.id, f"{sender.name}#{sender.discriminator}")
                currentUser = await getUser(sender.id)
            else:
                if currentUser.name != f"{sender.name}#{sender.discriminator}":
                    currentUser.name = f"{sender.name}#{sender.discriminator}"
                    await currentUser.pushChanges()

            if message.content == '/score':
                allUsers = await readAllSQL("SELECT * FROM arabicbot_user order by score DESC limit 25")
                text = "Top-25 users:"
                for n, user in enumerate(allUsers):
                    user = botUser(*user)
                    text = f"{text}\n{n + 1}) {user.name} - {user.score} points"
                text = f"{text}\n\nYou: {currentUser.score} points"
                await channel.send(text)
            if any(x in message.content for x in arabic):
                if settings.currentQuestion:
                    currentQuestion = await getQuestion(settings.currentQuestion)
                    if currentQuestion:
                        if currentId in currentUser.participatedIn:
                            await message.add_reaction('\N{Lock with Ink Pen}')
                            return
                        currentUser.participatedIn = [currentId]
                        if message.content == currentQuestion.answer or \
                                message.content.replace("؟", "?") == currentQuestion.answer \
                                or message.content.replace("?", "؟") == currentQuestion.answer:
                            await message.add_reaction('\N{Thumbs Up Sign}')
                            currentUser.score += currentQuestion.score
                            await currentUser.pushChanges()
                        else:
                            await message.add_reaction('\N{Thumbs Down Sign}')
                            await currentUser.pushChanges()
        else:
            if isinstance(channel, DMChannel):
                if sender.id == settings.ownerId or sender.id in settings.admins:
                    if settings.payload:
                        if message.content == "/cancel":
                            settings.payload = ''
                            await settings.pushChanges()
                            await channel.send('Ok, cancelled.')
                        if settings.payload == "waiting for new phrase":
                            if '->' not in message.content:
                                await channel.send("Wrong format. Send /cancel to cancel")
                                return
                            question, answer = message.content.split("->")
                            while answer.startswith(' '):
                                answer = answer[1:]
                            while answer.endswith(' '):
                                answer = answer[:-1]
                            while question.startswith(' '):
                                question = question[1:]
                            while question.endswith(' '):
                                question = question[:-1]
                            await execSQL("insert into arabicbot_question (question, answer) VALUES (?, ?)",
                                          question, answer)
                            lastInsertedRow = (await readOneSQL(
                                "select last_insert_rowid() from arabicbot_question"))[0]
                            await channel.send(f"Done, added to database with id `{lastInsertedRow}`")
                            settings.payload = ""
                            await settings.pushChanges()
                    elif message.content == '/new':
                        settings.payload = "waiting for new phrase"
                        await settings.pushChanges()
                        await channel.send("Okay, please send a new phrase in format:\n"
                                           "english phrase -> hebrew phrase\n`(with -> )`")
                    elif message.content == '/list':
                        allPhrases = await readAllSQL("select * from arabicbot_question")
                        text = 'here is a list of all questions -> answers:'
                        for phrase in allPhrases:
                            phrase = botQuestion(*phrase)
                            text = f"{text}\n{phrase.inDbId}) {phrase.question} -> {phrase.answer}"
                        await channel.send(text)
                    elif message.content == '/score':
                        allUsers = await readAllSQL("SELECT * FROM arabicbot_user order by score DESC limit 25")
                        currentUser = await getUser(sender.id)
                        if not currentUser:
                            await execSQL("insert into arabicbot_user (userId, name) "
                                          "VALUES (?, ?)", sender.id, f"{sender.name}#{sender.discriminator}")
                            currentUser = await getUser(sender.id)
                        else:
                            if currentUser.name != f"{sender.name}#{sender.discriminator}":
                                currentUser.name = f"{sender.name}#{sender.discriminator}"
                                await currentUser.pushChanges()
                        text = "Top-25 users:"
                        for n, user in enumerate(allUsers):
                            user = botUser(*user)
                            text = f"{text}\n{n + 1}) {user.name} - {user.score} points (`{user.userId}`)"
                        text = f"{text}\n\nYou: {currentUser.score} points"
                        await channel.send(text)
                    elif '/delete' in message.content:
                        whatToDelete = message.content.replace("/delete", "").replace(" ", "")
                        if not whatToDelete.isnumeric() or not (await getQuestion(int(whatToDelete))):
                            await channel.send("Could not find such id.")
                            return
                        await execSQL("delete from arabicbot_question where inDbId = ?", int(whatToDelete))
                        await channel.send("Done.")
                    elif '/reset' in message.content:
                        whatToDelete = message.content.replace("/reset", "").replace(" ", "")
                        if not whatToDelete.isnumeric():
                            await channel.send("Wrong user id format")
                            return
                        await execSQL("update arabicbot_user set score = 0, participatedIn = '[]' "
                                      "where userId = ?", int(whatToDelete))
                        await channel.send("Done.")
                    elif '/file' in message.content:
                        if message.attachments:
                            attachment = message.attachments[0]
                            if not attachment.filename.endswith('.txt'):
                                await channel.send("That shall be .txt file.")
                                return

                            response = await loop.run_in_executor(None, lambda: requests.get(attachment.url))
                            text = response.content.decode("UTF-8")
                            whatToAdd = []
                            # notDeleteIds = []
                            rows = text.split('\n')
                            for row in rows:
                                if not row:
                                    continue
                                if '->' in row:
                                    question, answer = row.split("->")
                                    question = question.replace("\r", '')
                                    answer = answer.replace("\r", '')
                                    while answer.startswith(' '):
                                        answer = answer[1:]
                                    while answer.endswith(' '):
                                        answer = answer[:-1]
                                    while question.startswith(' '):
                                        question = question[1:]
                                    while question.endswith(' '):
                                        question = question[:-1]
                                    whatToAdd.append(
                                        execSQL(
                                            "insert into arabicbot_question (question, answer) VALUES (?, ?)",
                                            question, answer))

                            if whatToAdd:
                                await execSQL('delete from  arabicbot_question')
                            else:
                                await channel.send('There was 0 questions, so that was ignored.')
                                return
                            for adding in whatToAdd:
                                await adding
                            await channel.send("Done.")

                        else:
                            await channel.send('No file attached.')
                    elif '/add_admin' in message.content and sender.id == settings.ownerId:
                        targetPerson = message.content.replace("/add_admin", "").replace(" ", "")
                        if not targetPerson.isnumeric():
                            await channel.send("Wrong user id format")
                            return
                        if int(targetPerson) not in settings.admins:
                            settings.admins.append(int(targetPerson))
                            await settings.pushChanges()
                        await channel.send("Done")
                    elif '/delete_admin' in message.content and sender.id == settings.ownerId:
                        targetPerson = message.content.replace("/delete_admin", "").replace(" ", "")
                        if not targetPerson.isnumeric():
                            await channel.send("Wrong user id format")
                            return
                        if int(targetPerson) in settings.admins:
                            settings.admins.remove(int(targetPerson))
                            await settings.pushChanges()
                        await channel.send("Done")
                    elif "/id" == message.content:
                        await channel.send(str(sender.id))
                    elif '/interval' in message.content:
                        targetTime = message.content.replace("/interval", "").replace(" ", "")
                        if not targetTime.isnumeric():
                            await channel.send("Wrong format, that should be numeric")
                            return
                        settings.interval = int(targetTime)
                        await settings.pushChanges()
                        await channel.send('Done')
                    else:
                        await channel.send("Hello there. Send`\n\n/new - to add a new phrase\n\n"
                                           "/list - to list all phrases (with delete ability)\n\n"
                                           "/score - to list top-25 scores & your\n\n/delete ID - "
                                           "to delete from database ("
                                           "example: `/delete 1` )\n\n/reset ID - to reset user's score to 0\n\n"
                                           "/file - set all questions to same as in the file\n\n/add_admin ID - "
                                           "add admin by ID\n\n/delete_admin ID - delete admin\n\n/id - get your id\n\n"
                                           "/interval MINUTES - change interval between questions (current interval is"
                                           f" {settings.interval} minutes)`")
                elif message.content == '/score':
                    allUsers = await readAllSQL("SELECT * FROM arabicbot_user order by score DESC limit 25")
                    currentUser = await getUser(sender.id)
                    if not currentUser:
                        await execSQL("insert into arabicbot_user (userId, name) "
                                      "VALUES (?, ?)", sender.id, f"{sender.name}#{sender.discriminator}")
                        currentUser = await getUser(sender.id)
                    else:
                        if currentUser.name != f"{sender.name}#{sender.discriminator}":
                            currentUser.name = f"{sender.name}#{sender.discriminator}"
                            await currentUser.pushChanges()
                    text = "Top-25 users:"
                    for n, user in enumerate(allUsers):
                        user = botUser(*user)
                        text = f"{text}\n{n + 1}) {user.name} - {user.score} points"
                    text = f"{text}\n\nYou: {currentUser.score} points"
                    await channel.send(text)
                elif "/id" == message.content:
                    await channel.send(str(sender.id))
            elif isinstance(channel, TextChannel):
                if message.content == '/set_channel' and sender.id == settings.ownerId:
                    settings.targetChannel = channel.id
                    for channel in self.get_all_channels():
                        channel: TextChannel
                        if channel.id == settings.targetChannel:
                            targetChannelInDiscord = channel
                            break
                    await channel.send("Done")
        # if not targetChannelInDiscord:
        #     print(message.channel.id)


async def postSomething():
    global targetChannelInDiscord, currentId
    await asyncio.sleep(1)
    lastPost = 0
    settings = await getSettings()
    interval = settings.interval * 60
    while True:
        if not targetChannelInDiscord:
            await asyncio.sleep(1)
            continue
        settings = await getSettings()
        interval = settings.interval * 60
        if int(time.time()) - lastPost > interval:
            allQuestions = await readAllSQL("select * from arabicbot_question")
            if not allQuestions:
                await asyncio.sleep(1)
                continue
            randomPicked = botQuestion(*random.choice(allQuestions))
            currentId = random.randrange(0, 1000000000)
            await targetChannelInDiscord.send(randomPicked.question)
            settings.currentQuestion = randomPicked.inDbId
            await settings.pushChanges()
            lastPost = int(time.time())
        await asyncio.sleep(1)


async def main():
    print('Checking database...')
    await execSQL(
        "create table if not exists arabicbot_settings (indDbId INTEGER DEFAULT 0 "
        "primary key, ownerId INTEGER DEFAULT 326190204, targetChannel INTEGER DEFAULT 0, "
        "currentQuestion INTEGER DEFAULT 0, `payload` STRING DEFAULT '', `value` STRING DEFAULT '{}', `interval`"
        " INTEGER DEFAULT 5, admins string default '[]')")
    await execSQL(
        "create table if not exists arabicbot_user (userId INTEGER DEFAULT"
        " 0 primary key, score DOUBLE DEFAULT 0, `participatedIn` STRING DEFAULT '[]', `name` default '')")
    await execSQL(
        "create table if not exists arabicbot_question (inDbId INTEGER DEFAULT "
        "0 primary key autoincrement , score DOUBLE DEFAULT 1.0, "
        "`question` STRING DEFAULT '', `answer` STRING DEFAULT '')")
    #print(await readAllSQL("select * from arabicbot_question"))
    print('Starting bot...')
    settings_counts= len(await readAllSQL("select * from arabicbot_settings"))
    print(conf.OWNERID)
    print(conf.CHANNELID)
    print(conf.INTERVAL)
    #print(conf.TOKEN)
    if settings_counts == 0:
        id=1
        ownerId = conf.OWNERID
        targetChannel = conf.CHANNELID
        interval = conf.INTERVAL
        admin = '[' + str(conf.OWNERID) + ']'
        await execSQL(
        "INSERT INTO arabicbot_settings  (ownerId,targetChannel,currentQuestion,payload,value,interval,admins) VALUES (?,?,?,?,?,?,?)",
           ownerId, targetChannel, 10,'', '{}', interval,admin)
    #settings =  botSettings(1,681085330493145093,681323265297612869,10,'',1,"{}",admin );
    #await settings.pushChanges();
    #print('Stopping bot...')
    #settings.admins.append(int(12345))
    #await settings.pushChanges()
    await asyncio.gather(client.start(conf.ID), postSomething())



client = MyClient()
loop = asyncio.get_event_loop()
loop.run_until_complete(main())
