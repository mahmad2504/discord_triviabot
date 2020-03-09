# bot.py
import os
import discord
import tracemalloc
import logging
import asyncio
import requests
import random
import sqlite3
import signal
import json
import operator
#import threading

from discord.message import Message
from discord.channel import CategoryChannel, TextChannel, VoiceChannel, DMChannel
from discord.guild import Guild
from discord.member import Member
from signal import signal, SIGINT
from sys import exit


TOKEN=os.environ['DISCORD_TOKEN']
ADMIN_ID=os.environ['ADMIN_ID']
ADMIN_ID2=os.environ['ADMIN_ID2']
TIME_OUT=2000  #SECOND
instances = {};

def handler(signal_received, frame):
    # Handle any cleanup here
    print('SIGINT or CTRL-C detected. Exiting gracefully')
    exit(0)


async def execSQL(sql, *args):
    return await loop.run_in_executor(None, lambda: dbConnection.cursor().execute(sql, args))

async def readAllSQL(sql, *args):
    data = await loop.run_in_executor(None, lambda: dbConnection.cursor().execute(sql, args).fetchall())
    return data
	
async def readOneSQL(sql, *args):
    data = await loop.run_in_executor(None, lambda: dbConnection.cursor().execute(sql, args).fetchone())
    return data

def GetInstance(channel):
    global instances
    table="question_"+channel.name
    if channel.id in instances: 
        return instances[channel.id]
    return None

async def CreateInstance(channel):
    global TIME_OUT,instances
    table="question_"+str(channel.id)
    instance = {}
    instance['question_count']=0
    instance['channel']=channel
    instance['question'] = None;
    instance['timer'] = 0
    instance['time_out'] = TIME_OUT
    instance['active']=0;
    instance['score']={};
    instances[channel.id]= instance;
    
    questions_table="question_"+str(channel.id)
    settings_table="settings_"+str(channel.id)
        
        
    await execSQL(
    "create table if not exists "+questions_table+" (inDbId INTEGER DEFAULT "
    "0 primary key autoincrement , number INTEGER , "
    "`question` STRING DEFAULT '', `answer` STRING DEFAULT '')")
        
    await execSQL(
    "create table if not exists "+settings_table+" (inDbId INTEGER DEFAULT "
    "0 primary key autoincrement ,"
    "`settings` STRING DEFAULT '')")
    
    query="select * from "+settings_table
    record = await readOneSQL(query);
    if record==None:
        return instance
        
    text=json.loads(record[1])
    
    instance['time_out']=text['time_out']
    instance['score']=text['score']
    
    return instance
    
async def CheckAnswer(instance,message):
    actualanswer = instance['question'][3]
    #print(actualanswer)
    if message.content.lower() == actualanswer.lower() or \
                                message.content.replace("؟", "?").lower() == actualanswer.lower() \
                                or message.content.replace("?", "؟").lower() == actualanswer.lower():
        await message.add_reaction('\N{Thumbs Up Sign}')
        return 1
    return 0
    #await message.channel.send(actualanswer);   
    #await message.add_reaction('\N{Thumbs Up Sign}')


async def ClearScore(instance):
    instance['score'] = {}
    await UpdateScore(instance,None)
    
async def UpdateScore(instance,author):
    if author is not None:
    if author in instance['score'].keys(): 
        instance['score'][author] = instance['score'][author] + 1
    else:
        instance['score'][author]=1
    save ={};
    save['score'] = instance['score'];
    save['time_out'] = instance['time_out'];
    instance_str = json.dumps(save)
    settings_table="settings_"+str(instance['channel'].id)
    await execSQL('delete from  '+settings_table)
    whatToAdd = []
    whatToAdd.append(
	               execSQL(
		           "insert into "+settings_table+" (settings) VALUES (?)",
		           instance_str))
    for adding in whatToAdd:
        await adding
                                
    #print(instance_str);
   
 
async def SetQuestion(instance):
    table="question_"+str(instance['channel'].id)
    query = "select count(*) from "+table;
    question_count = await readOneSQL(query)
    if question_count[0]==0:
        return 0
    instance['question_count']=question_count[0]
    qid = random.randrange(1, question_count[0]+1)
    query="select * from "+table+" where number="+str(qid);
    question = await readAllSQL(query)
    instance['question'] = list(question[0]);
    return 1
    
    
async def AskQuestion(instance):
    await instance['channel'].send(instance['question'][2])

def SetTimeout(instance,timeout):
   instance['time_out'] = timeout
   instance['timer']=0;
def IncrementTimer(instance):
    instance['timer'] = instance['timer']+1
    if instance['timer'] > instance['time_out']:
        instance['timer'] = 0
        return 0
    return 1;
def ExpireTimer(instance):
    instance['timer'] = instance['time_out']
    
def Activate(instance):
   instance['active'] = 1
   instance['timer'] = instance['time_out']

def DeActivate(instance):
   instance['active'] = 0

def IsActive(instance):
    return instance['active']

class MyClient(discord.Client):	
    async def on_ready(client):
        #print(f'{client .user} has connected to Discord!')
        #for guild in client .guilds:
            ##print(client .name)
            ##print(client .id)
            #if guild.id == GUILD:
            #    break
        #members = '\n - '.join([member.name for member in guild.members])
        #print(
        #    f'{client.user} is connected to the following guild:\n'
        #    f'{guild.name}(id: {guild.id})\n'
        #)
        #print(f'Guild Members:\n - {members}')
        for channel in client.get_all_channels():
            #if channel.name in channels:
            if channel.category is None:
                continue;
            if channel.category.name=='Text Channels':
                #print("name is "+channel.name)
                await channel.send("Hi, trivia bot is activated!")

    #async def on_member_join(client, member: discord.Member):
        #await member.create_dm()
        #await member.dm_channel.send(f'Hi {member.name}, welcome to my Discord server!')

    async def on_message(client, message: Message):
        global channels
        if message.author == client.user:
            return
        instance= GetInstance(message.channel)
            
        if 1:
            #str(message.channel) in channels:
            #print(message.author)
            #print(message.content)
            #await message.add_reaction('\N{Thumbs Down Sign}')
            #await message.channel.send("Hi") 
            table="question_"+message.channel.name
            #print(message.author.id)
            if '/start' in message.content:  
                if instance is not None:
                    if IsActive(instance):
                        await message.channel.send('Trivia is already active')
                        return;
                    else:
                        Activate(instance)
                        await SetQuestion(instance);
                        return
                instance = await CreateInstance(message.channel);
                result = await SetQuestion(instance);
                if result==0:
                    await message.channel.send('No questions in database\nTrivia cannot start')
                    return;
                Activate(instance);
                await message.channel.send('Trivia is started')
            elif '/stop' in message.content:
                if instance is None:
                    await message.channel.send('No Trivia is loaded')
                    return;
                DeActivate(instance);
                await message.channel.send('Trivia is stopped')
            elif '/score' in message.content:
                if instance is None:
                    await message.channel.send('No Trivia is loaded')
                    return;
                
                text = "Top-10 users:\n\n"
                #scores = sorted(instance['score'].values())
                sorted_d = sorted(instance['score'].items(), key=operator.itemgetter(1))
                for a, b in sorted_d:
                    text = f"{text}{a}: {b} points\n"
                
                await message.channel.send(text)
                
            else:
                if instance is not None:
                    if IsActive(instance):
                        score = await CheckAnswer(instance,message)
                        if score==1:
                            await UpdateScore(instance,message.author.name);
                            await SetQuestion(instance);
                            ExpireTimer(instance);
            if str(message.author.id)  == str(ADMIN_ID) or str(message.author.id)  == str(ADMIN_ID2):
                if message.attachments:
                    await HandleFileUploadCommand(message);
                elif '/clearscore' in message.content:
                    await ClearScore(instance)
                    await message.channel.send('Scores are successfully deleted')
                elif '/interval' in message.content:
                    if instance is None:
                        await message.channel.send('No Trivia is loaded')
                        return;
                    targetTime = message.content.replace("/interval", "").replace(" ", "")
                    if not targetTime.isnumeric():
                        await channel.send("Wrong format, that should be numeric")
                        return
                    SetTimeout(instance,int(targetTime))
                    await message.channel.send('Timeout set to '+targetTime+' sec')
                    
async def HandleFileUploadCommand(message):
    #print("Command::File Upload")
    if message.attachments:
        attachment = message.attachments[0]
        if not attachment.filename.endswith('.txt'):
            await message.channel.send("That shall be .txt file.")
            return
        response = await loop.run_in_executor(None, lambda: requests.get(attachment.url))
        text = response.content.decode("UTF-8")
        whatToAdd = []
        rows = text.split('\n')
        i=0
        
        questions_table="question_"+str(message.channel.id)
        settings_table="settings_"+str(message.channel.id)
        
        await execSQL(
        "create table if not exists "+questions_table+" (inDbId INTEGER DEFAULT "
        "0 primary key autoincrement , number INTEGER , "
        "`question` STRING DEFAULT '', `answer` STRING DEFAULT '')")
        
        await execSQL(
        "create table if not exists "+settings_table+" (inDbId INTEGER DEFAULT "
        "0 primary key autoincrement ,"
        "`settings` STRING DEFAULT '')")
        
        
        for row in rows:
            if not row:
                continue
            if '->' in row:	
                i=i+1			
                question, answer = row.split("->")
                question = question.replace(u'\ufeff', '')
                #print(question)
                #print(answer)
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
		           "insert into "+questions_table+" (number,question, answer) VALUES (?, ?, ?)",
		           i,question, answer))
        if len(whatToAdd) == 0: 
            await message.channel.send('No questions found')
            return
		
        await execSQL('delete from  '+questions_table)
		
        for adding in whatToAdd:
            await adding
        
        await message.channel.send("Trivia quiz uploaded")
        await message.channel.send("Type /start to start trivia quiz")
    else:
        await message.channel.send('No file attached.')
		
async def postSomething():
    global timer_counter,time_out,question_count,current_question
    while True:
        await asyncio.sleep(1)
        for key in instances:
            instance = instances[key]
            if IsActive(instance)==0:
                continue;
            if IncrementTimer(instance)==0: #timeout
                await AskQuestion(instance)
                
           
        continue

	
async def main():
   await asyncio.gather(client.start(TOKEN), postSomething())

signal(SIGINT, handler)
tracemalloc.start()
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',level=logging.WARN)
logger = logging.getLogger(__name__)
scriptName = str(os.path.basename(__file__).split(".")[0])
print("Starting Bot script", scriptName)
dbConnection = sqlite3.connect(f"data_{scriptName}.db", isolation_level=None, check_same_thread=False)


#def watchdog():
#  print('Watchdog expired. Exiting...')
  

#alarm = threading.Timer(3, watchdog)
#alarm.start()
#alarm.cancel()
#alarm = threading.Timer(8, watchdog)
#alarm.start()




client = MyClient()
loop = asyncio.get_event_loop()
loop.run_until_complete(main())