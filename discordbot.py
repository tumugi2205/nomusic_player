import os
import asyncio
import youtube_dl
import requests
from discord.ext import tasks
import discord
import traceback
import json

 
token = os.environ['DISCORD_BOT_TOKEN']
DEBUG=""

# Suppress noise about console usage from errors
youtube_dl.utils.bug_reports_message = lambda: ''

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': os.path.join(os.path.dirname(os.path.abspath(__file__)), "tmp", '%(extractor)s-%(id)s-%(title)s.%(ext)s'),
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0' # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ffmpeg_options = {
    'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.01):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        player = discord.FFmpegPCMAudio(filename, **ffmpeg_options)
        return player, data.get('title')
        
client = discord.Client()

# {"user": str, "player": player, "title": str}
play_list=[]
play_now=[]
play_flag = [True]
loop_flag = [False]
default_msg = []

# 連続再生する機能
@tasks.loop(seconds=1)
async def loop(message):
    message = default_msg[0]
    if not message.guild.voice_client.is_playing() and (not len(play_list)==0 or loop_flag[0]) and play_flag[0]:
        if loop_flag[0]:
            try:
                embed = discord.Embed(title="loop plaing♪", description=f'{play_now[0]["title"]}  by:{play_now[0]["user"]}' ,color=0x4169e1)
                await message.channel.send(embed=embed)
                player, title = await YTDLSource.from_url(play_now[0]["url"], loop=client.loop)
                message.guild.voice_client.play(player)
            except Exception as e:
                embed = discord.Embed(title=f'error: {e}', description=f'info: {traceback.format_exc()}' ,color=0x4169e1)
                await message.channel.send(embed=embed)
        else:
            try:
                plaing = play_list.pop(0)
                if len(play_now)>0:
                    play_now.pop(0)
                play_now.append(plaing)
                embed = discord.Embed(title="now plaing♪", description=f'{plaing["title"]}  by:{plaing["user"]}' ,color=0x4169e1)
                await message.channel.send(embed=embed)
                message.guild.voice_client.play(plaing["player"])
            except Exception as e:
                await message.channel.send(f'error: {e}')
                await message.channel.send(f'info: {traceback.format_exc()}')
            

@client.event
async def on_message(message: discord.Message):
    # メッセージの送信者がbotだった場合は無視する
    if message.author.bot:
        return

    if message.content == f"!j{DEBUG}":
        print(message.guild.voice_client)
        if message.author.voice is None:
            embed = discord.Embed(description="あなたはボイスチャンネルに接続していません。", color=0x4169e1)
            await message.channel.send(embed=embed)
            return
        # ボイスチャンネルに接続する
        await message.author.voice.channel.connect()
        embed = discord.Embed(description="接続しました。", color=0x4169e1)
        await message.channel.send(embed=embed)
        default_msg.append(message)
        loop.start(message)
    elif message.content == f"!l{DEBUG}":
        if message.guild.voice_client is None:
            embed = discord.Embed(description="接続していません。", color=0x4169e1)
            await message.channel.send(embed=embed)
            return

        # 切断する
        await message.guild.voice_client.disconnect()
        embed = discord.Embed(description="切断しました。", color=0x4169e1)
        await message.channel.send(embed=embed)
    elif message.content.startswith(f"!pl{DEBUG} "):
        if message.author.voice is None:
            embed = discord.Embed(description="あなたはボイスチャンネルに接続していません。", color=0x4169e1)
            await message.channel.send(embed=embed)
            return
        if message.guild.voice_client is None:
            # ボイスチャンネルに接続する
            await message.author.voice.channel.connect()
            embed = discord.Embed(description="接続しました。", color=0x4169e1)
            await message.channel.send(embed=embed)
            default_msg.append(message)
            loop.start(message)
        url = message.content.split(f" ")[-1]
        player, title = await YTDLSource.from_url(url, loop=client.loop)
        play_list.append({"user": message.author.name, "player": player, "title": title, "url": url})
    elif message.content == f"!next{DEBUG}":
        loop_flag.pop(0)
        loop_flag.append(False)
        if message.guild.voice_client is None:
            await message.channel.send()
            embed = discord.Embed(description="接続していません。", color=0x4169e1)
            await message.channel.send(embed=embed)
            return
        # 再生中ではない場合は実行しない
        if not message.guild.voice_client.is_playing():
            embed = discord.Embed(description="再生していません。", color=0x4169e1)
            await message.channel.send(embed=embed)
            return
        message.guild.voice_client.stop()
        embed = discord.Embed(description="ストップしました。", color=0x4169e1)
        await message.channel.send(embed=embed)
    elif message.content.startswith(f"!mp{DEBUG}"):
        if message.guild.voice_client is None:
            embed = discord.Embed(description="接続していません。", color=0x4169e1)
            await message.channel.send(embed=embed)
            return
        d = message.attachments.pop(0)
        filename = str(d).split("/")[-1]
        r = requests.get(str(d), stream=True)
        if r.status_code == 200:
            with open(filename, 'wb') as f:
                f.write(r.content)
        play_list.append({"user": message.author.name, "player": discord.FFmpegPCMAudio(filename), "title": filename})
    elif message.content == f"!stop{DEBUG}":
        play_flag.pop(0)
        play_flag.append(False)
        if message.guild.voice_client is None:
            embed = discord.Embed(description="接続していません。", color=0x4169e1)
            await message.channel.send(embed=embed)
            return
        # 再生中ではない場合は実行しない
        if not message.guild.voice_client.is_playing():
            embed = discord.Embed(description="再生していません。", color=0x4169e1)
            await message.channel.send(embed=embed)
            return
        message.guild.voice_client.stop()
        embed = discord.Embed(description="ストップしました。", color=0x4169e1)
        await message.channel.send(embed=embed)
        if loop_flag[0]:
            loop_flag.pop(0)
            loop_flag.append(False)
            embed = discord.Embed(description="ループ再生を終了しました。", color=0x4169e1)
            await message.channel.send(embed=embed)
    elif message.content == f"!start{DEBUG}":
        play_flag.pop(0)
        play_flag.append(True)
    elif message.content.startswith(f"!in{DEBUG} "):
        if message.author.voice is None:
            embed = discord.Embed(description="あなたはボイスチャンネルに接続していません。", color=0x4169e1)
            await message.channel.send(embed=embed)
            return
        if message.guild.voice_client is None:
            # ボイスチャンネルに接続する
            await message.author.voice.channel.connect()
            embed = discord.Embed(description="接続しました。", color=0x4169e1)
            await message.channel.send(embed=embed)
            default_msg.append(message)
            loop.start(message)
        url = message.content.split(f" ")[-1]
        player, title = await YTDLSource.from_url(url, loop=client.loop)
        play_list.insert(0, {"user": message.author.name, "player": player, "title": title, "url": url})
    elif message.content.startswith(f"!playlist{DEBUG}"):
        if "-i" in message.content.split(f" "):
            embed = discord.Embed(title=f"now♪ > {play_now[0]['title']}", description=f"by{play_now[0]['user']} [リンク]({play_now[0]['url']})",color=0x4169e1)
            mov_id = play_now[0]['url'].replace("https://www.youtube.com/watch?v=", "").split("&")[0]
            embed.set_image(url=f"https://img.youtube.com/vi/{mov_id}/0.jpg")
            await message.channel.send(embed=embed)
            for d in play_list:
                embed = discord.Embed(title=f"now♪ > {d['title']}", description=f"by{d['user']} [リンク]({play_now[0]['url']})",color=0x4169e1)
                mov_id = d['url'].replace("https://www.youtube.com/watch?v=", "").split("&")[0]
                embed.set_image(url=f"https://img.youtube.com/vi/{mov_id}/0.jpg")
                await message.channel.send(embed=embed)
        else:
            embed = discord.Embed(title="playlist",color=0x4169e1)
            embed.add_field(name=f"now♪ > {play_now[0]['title']}", value=f"by{play_now[0]['user']}",inline=False)
            for d in play_list:
                embed.add_field(name=d['title'], value=f"by{d['user']}",inline=False)
            await message.channel.send(embed=embed)

    elif message.content.startswith(f"!now{DEBUG}"):
        embed = discord.Embed(title=f"now♪ > {play_now[0]['title']}", description=f"by{play_now[0]['user']} [リンク]({play_now[0]['url']})",color=0x4169e1)
        mov_id = play_now[0]['url'].replace("https://www.youtube.com/watch?v=", "").split("&")[0]
        embed.set_image(url=f"https://img.youtube.com/vi/{mov_id}/0.jpg")
    elif message.content.startswith(f"!loop{DEBUG}"):
        loop_flag.pop(0)
        loop_flag.append(True)
        embed = discord.Embed(title=f"{play_now[0]['title']}", description=f"ループ再生します。", color=0x4169e1)
        await message.channel.send(embed=embed)
    elif message.content.startswith(f"!stoploop{DEBUG}"):
        loop_flag.pop(0)
        loop_flag.append(False)
        embed = discord.Embed(title=f"{play_now[0]['title']}", description=f"ループを終了します。", color=0x4169e1)
        await message.channel.send(embed=embed)
    elif message.content == f"!h{DEBUG}":
        # コマンドヘルプ
        embed = discord.Embed(title="ヘルプ", description="コマンド一覧", color=0x4169e1)
        embed.add_field(name="!h", value="ヘルプコマンド。今見てるだろ。")
        embed.add_field(name="!j", value="BOTを通話に入れる。")
        embed.add_field(name="!l", value="BOTを通話から出す。でてけー")
        embed.add_field(name="!pl {youtube url}", value="youtubeの動画音声を流す。")
        embed.add_field(name="!next", value="次の曲を再生する。何もなかったら終了。")
        embed.add_field(name="!stop", value="曲停止。今再生されてる曲は飛ばされる。")
        embed.add_field(name="!start", value="曲再生。再生中なら特に何もなし")
        embed.add_field(name="!mp {添付}", value="添付ファイルの曲を流す。mp3では動作確認してる。")
        embed.add_field(name="!playlist", value="play list を表示する。")
        embed.add_field(name="!playlist -i", value="play list をサムネ付きで表示する。")
        await message.channel.send(embed=embed)
        return



client.run(token)