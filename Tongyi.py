import os

import wx
from openai import OpenAI
from PIL import Image
import base64
import io
import cv2
import dashscope
import soundfile as sf
import librosa
import numpy as np

# 设置API密钥
dashscope.api_key = "sk-13347f16eefa41abb9d6dd02df4c53ad"

class ChatFrame(wx.Frame):
    def __init__(self):
        super().__init__(parent=None, title='通义千问对话', size=(800, 600))
        
        # 创建OpenAI客户端
        self.client = OpenAI(
            api_key="sk-13347f16eefa41abb9d6dd02df4c53ad",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        
        # 存储对话历史
        self.messages = [{'role': 'system', 'content': 'You are a helpful assistant.'}]
        
        # 当前选择的文件
        self.current_file = None
        self.current_image_base64 = None
        self.is_video = False
        self.is_audio = False
        self.video_frames = None
        self.audio_content = None
        
        # 创建界面
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        # 对话历史文本框
        self.history = wx.TextCtrl(panel, style=wx.TE_MULTILINE|wx.TE_READONLY)
        vbox.Add(self.history, 1, wx.EXPAND|wx.ALL, 5)
        
        # 文件路径显示区域
        hbox_path = wx.BoxSizer(wx.HORIZONTAL)
        self.path_text = wx.TextCtrl(panel, style=wx.TE_READONLY)
        self.path_text.Bind(wx.EVT_KEY_DOWN, self.on_key_down)
        self.quick_send_btn = wx.Button(panel, label='直接发送')
        self.quick_send_btn.Bind(wx.EVT_BUTTON, self.on_quick_send)
        hbox_path.Add(self.path_text, 1, wx.EXPAND|wx.ALL, 5)
        hbox_path.Add(self.quick_send_btn, 0, wx.ALL, 5)
        vbox.Add(hbox_path, 0, wx.EXPAND)
        self.path_text.Hide()
        self.quick_send_btn.Hide()
        
        # 输入框和按钮
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        self.input = wx.TextCtrl(panel)
        self.send_btn = wx.Button(panel, label='发送')
        self.img_btn = wx.Button(panel, label='选择图片')
        self.video_btn = wx.Button(panel, label='选择视频')
        self.audio_btn = wx.Button(panel, label='选择音频(未完善)')
        self.clear_btn = wx.Button(panel, label='清除文件')
        self.send_btn.Bind(wx.EVT_BUTTON, self.on_send)
        self.img_btn.Bind(wx.EVT_BUTTON, self.on_choose_image)
        self.video_btn.Bind(wx.EVT_BUTTON, self.on_choose_video)
        self.audio_btn.Bind(wx.EVT_BUTTON, self.on_choose_audio)
        self.clear_btn.Bind(wx.EVT_BUTTON, self.clear_file)
        hbox.Add(self.input, 1, wx.EXPAND|wx.ALL, 5)
        hbox.Add(self.img_btn, 0, wx.ALL, 5)
        hbox.Add(self.video_btn, 0, wx.ALL, 5)
        hbox.Add(self.audio_btn, 0, wx.ALL, 5)
        hbox.Add(self.clear_btn, 0, wx.ALL, 5)
        hbox.Add(self.send_btn, 0, wx.ALL, 5)
        vbox.Add(hbox, 0, wx.EXPAND)
        
        panel.SetSizer(vbox)
        self.Show()
        
    def image_to_base64(self, image_path):
        with Image.open(image_path) as img:
            if img.mode != 'RGB':
                img = img.convert('RGB')
            max_size = 1024
            if max(img.size) > max_size:
                ratio = max_size / max(img.size)
                img = img.resize((int(img.size[0] * ratio), int(img.size[1] * ratio)))
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG')
            return base64.b64encode(buffer.getvalue()).decode('utf-8')
            
    def video_to_frames(self, video_path):
        frames = []
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        interval = max(1, int(total_frames / 10))  # 抽取10帧
        
        count = 0
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            if count % interval == 0:
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(rgb_frame)
                buffer = io.BytesIO()
                pil_img.save(buffer, format='JPEG')
                base64_frame = base64.b64encode(buffer.getvalue()).decode('utf-8')
                frames.append(base64_frame)
            count += 1
        cap.release()
        return frames
            
    def clear_file(self, event=None):
        self.current_file = None
        self.current_image_base64 = None
        self.is_video = False
        self.is_audio = False
        self.video_frames = None
        self.audio_content = None
        self.path_text.Hide()
        self.quick_send_btn.Hide()
        self.Layout()
        
    def on_key_down(self, event):
        keycode = event.GetKeyCode()
        if keycode == wx.WXK_DELETE:
            self.clear_file()
        event.Skip()
        
    def on_choose_image(self, event):
        with wx.FileDialog(self, "选择图片", wildcard="图片文件 (*.jpg;*.png)|*.jpg;*.png",
                         style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            image_path = fileDialog.GetPath()
            self.current_file = image_path
            self.current_image_base64 = self.image_to_base64(image_path)
            self.is_video = False
            self.is_audio = False
            self.path_text.SetValue(image_path)
            self.path_text.Show()
            self.quick_send_btn.Show()
            self.Layout()
            
    def on_choose_video(self, event):
        with wx.FileDialog(self, "选择视频", wildcard="视频文件 (*.mp4;*.avi)|*.mp4;*.avi",
                         style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            video_path = fileDialog.GetPath()
            self.current_file = video_path
            self.is_video = True
            self.is_audio = False
            self.video_frames = self.video_to_frames(video_path)
            self.path_text.SetValue(video_path)
            self.path_text.Show()
            self.quick_send_btn.Show()
            self.Layout()
            
    def on_choose_audio(self, event):
        with wx.FileDialog(self, "选择音频", wildcard="音频文件 (*.mp3;*.wav)|*.mp3;*.wav",
                         style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            audio_path = fileDialog.GetPath()
            self.current_file = audio_path
            self.is_video = False
            self.is_audio = True
            
            # 使用librosa读取音频内容
            try:
                # 使用librosa加载音频
                audio, sr = librosa.load(audio_path, sr=None)
                # 转换为临时wav文件
                temp_wav = "temp_audio.wav"
                sf.write(temp_wav, audio, sr)
                
                messages = [
                    {
                        "role": "user",
                        "content": [
                            {"audio": f"file://{temp_wav}"},
                            {"text": "请提取音频内容"}
                        ]
                    }
                ]
                response = dashscope.MultiModalConversation.call(
                    model="qwen-audio-turbo-latest",
                    messages=messages
                )
                
                # 删除临时文件
                if os.path.exists(temp_wav):
                    os.remove(temp_wav)
                    
                if response and hasattr(response, 'output') and hasattr(response.output, 'choices'):
                    self.audio_content = response.output.choices[0].message.content[0]['text']
                else:
                    self.audio_content = None
            except Exception as e:
                self.audio_content = None
                print(f"音频处理错误: {str(e)}")
                
            self.path_text.SetValue(audio_path)
            self.path_text.Show()
            self.quick_send_btn.Show()
            self.Layout()
            
    def on_quick_send(self, event):
        if self.current_file:
            self.input.SetValue("")
            self.on_send(event)
        
    def on_send(self, event):
        user_input = self.input.GetValue()
        
        if not user_input and not self.current_file:
            return
            
        self.input.SetValue("")
        
        if self.current_file:
            if self.is_video:
                self.history.AppendText(f"用户: {user_input} [视频: {self.current_file}]\n")
                
                # 首先处理视频帧
                message_content = [{"type": "text", "text": user_input if user_input else "这个视频是什么内容?"}]
                for frame in self.video_frames:
                    message_content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{frame}"}})
                    
                video_completion = self.client.chat.completions.create(
                    model="qwen-vl-max-latest",
                    messages=[{"role": "user", "content": message_content}]
                )
                
                video_understanding = video_completion.choices[0].message.content
                
                # 处理视频的音频部分
                try:
                    # 使用librosa提取音频
                    audio, sr = librosa.load(self.current_file, sr=None)
                    temp_wav = "temp_video_audio.wav"
                    sf.write(temp_wav, audio, sr)
                    
                    messages = [
                        {
                            "role": "user",
                            "content": [
                                {"audio": f"file://{temp_wav}"},
                                {"text": "请提取音频内容"}
                            ]
                        }
                    ]
                    audio_response = dashscope.MultiModalConversation.call(
                        model="qwen-audio-turbo-latest",
                        messages=messages
                    )
                    
                    # 删除临时文件
                    if os.path.exists(temp_wav):
                        os.remove(temp_wav)
                    
                    if audio_response and hasattr(audio_response, 'output') and hasattr(audio_response.output, 'choices'):
                        audio_understanding = audio_response.output.choices[0].message.content[0]['text']
                    else:
                        audio_understanding = "无法识别音频内容"
                except Exception as e:
                    audio_understanding = f"音频处理出错: {str(e)}"
                
                # 结合视频和音频理解生成最终回答
                final_prompt = f"基于视频画面理解：{video_understanding}\n基于音频理解：{audio_understanding}\n请综合分析并回答用户问题：{user_input if user_input else '这个视频是什么内容?'}"
                
                final_completion = self.client.chat.completions.create(
                    model="qwen-plus",
                    messages=[{"role": "user", "content": final_prompt}]
                )
                
                assistant_reply = final_completion.choices[0].message.content
                
            elif self.is_audio:
                self.history.AppendText(f"用户: [音频: {self.current_file}]\n")
                
                try:
                    # 使用librosa加载音频
                    audio, sr = librosa.load(self.current_file, sr=None)
                    temp_wav = "temp_audio.wav"
                    sf.write(temp_wav, audio, sr)
                    
                    messages = [
                        {
                            "role": "user", 
                            "content": [
                                {"audio": f"file://{temp_wav}"},
                                {"text": user_input if user_input else "音频里在说什么?"}
                            ]
                        }
                    ]
                    
                    response = dashscope.MultiModalConversation.call(
                        model="qwen-audio-turbo-latest",
                        messages=messages
                    )
                    
                    # 删除临时文件
                    if os.path.exists(temp_wav):
                        os.remove(temp_wav)
                    
                    if response and hasattr(response, 'output') and hasattr(response.output, 'choices'):
                        assistant_reply = response.output.choices[0].message.content[0]['text']
                    else:
                        assistant_reply = "抱歉,音频处理失败"
                except Exception as e:
                    assistant_reply = f"处理音频时出错: {str(e)}"
                
            else:
                self.history.AppendText(f"用户: {user_input} [图片: {self.current_file}]\n")
                message_content = [
                    {"type": "text", "text": user_input if user_input else "这张图片是什么?"},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{self.current_image_base64}"}}
                ]
                
                completion = self.client.chat.completions.create(
                    model="qwen-vl-max-latest",
                    messages=[{"role": "user", "content": message_content}]
                )
                assistant_reply = completion.choices[0].message.content
            
        else:
            self.history.AppendText(f"用户: {user_input}\n")
            self.messages.append({'role': 'user', 'content': user_input})
            
            completion = self.client.chat.completions.create(
                model="qwen-plus",
                messages=self.messages
            )
            assistant_reply = completion.choices[0].message.content
        
        self.history.AppendText(f"助手: {assistant_reply}\n")
        
        if not self.current_file:
            self.messages.append({'role': 'assistant', 'content': assistant_reply})

if __name__ == '__main__':
    app = wx.App()
    frame = ChatFrame()
    app.MainLoop()