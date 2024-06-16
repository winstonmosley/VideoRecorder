import sounddevice as sd
import soundfile as sf
import numpy  # Make sure NumPy is loaded before it is used in the callback
assert numpy  # avoid "imported but unused" message (W0611)
from picamera2 import Picamera2
from picamera2.encoders import H264Encoder, Quality
from picamera2.outputs import FileOutput, FfmpegOutput
import time
from datetime import datetime, timedelta
from signal import pause
from gpiozero import Button, RGBLED, CPUTemperature
import queue
import threading
import os
import sys
import logging

os.environ["LIBCAMERA_LOG_LEVELS"] = "3" #suppress obnoxious camera warnings
os.chdir('/home/winston')

button = Button(16, hold_time=3)
sample_rate = 44100 #Hz
dev_index = 0 #select lavalier mic from sd.query_devices()
chans = 1 #number of audio channels to record
sd.default.samplerate = sample_rate
sd.default.channels = chans

resolution = [720, 1280] #[1080, 1920] #width and height in pixels
framerate = 24 #frames per second
segment_length = 10 #minutes between autosave
sleep_interval = 1 #seconds sleep between checking
qual = Quality.VERY_HIGH

q = queue.Queue()

def button_press():
    global recording, shutdown_initiated
    recording = not(recording) #toggle recording state
    if shutdown_initiated: recording = False #enforce no more recording if shutting down
    if recording == True: #start recording audio & video
        time.sleep(1)
        thread = threading.Thread(target=AV_rec)
        thread.start()

def button_hold():
    global recording, shutdown_initiated, led
    print('\n\n *initiating shutdown* \n\n')
    recording = False
    shutdown_initiated = True
    led.blink(on_time=.3, off_time=.2, on_color=(1,0,0), n=3) #visually indicate OFF status
    time.sleep(15) #wait for everything to shutdown
    os.system("sudo shutdown now")
    
def callback(indata, frames, time, status):
    """This is called (from a separate thread) for each audio block."""
    if status:
        print(status, file=sys.stderr)
    q.put(indata.copy())

def AV_rec():
    global recording, picam2, arec, vrec, led
    
    segment = 0
    ts0 = datetime.now()
    timestamp = datetime.now().strftime("%y-%m-%d_%H'%M'%S")
    arec = True
    vrec = True
    
    print('A'*10,'V'*10,'>'*20)
    print('Recording audio and video....')
    print('Enable time:', ts0.strftime('%H:%M:%S.%f'))
    
    logging.info(f"\tLogging CPU Temperature for recording starting at {timestamp}")
    cpu = CPUTemperature() 
    
    led.blink(on_time=1, off_time=1, on_color=(0,1,0), n=3) #visually indicate ON status
    while recording:
        print('*****Recording segment',segment+1)
        suffix = str(int(segment*segment_length))

        afilename = f"./unsent_files/{timestamp}+{suffix}min_A.wav"
        vfilename = f"./unsent_files/{timestamp}+{suffix}min_V.h264"
        #output = FileOutput(filename)
        picam2.start_recording(encoder, vfilename, quality=qual)
        file = sf.SoundFile(afilename, mode='x', samplerate=sample_rate, channels=chans)
        
        logging.info(f"\t\tCPU Temperature is {cpu.temperature} degC")
        
        ts1 = datetime.now()
        ts = ts1        
        with sd.InputStream(samplerate=sample_rate, device=dev_index, blocksize=1024, channels=chans, callback=callback):
            while recording & ((ts-ts1)<dt): #check if recording canceled or segment duration surpassed
                #time.sleep(sleep_interval) #wait until next checkwhile recording:
                file.write(q.get())
                ts = datetime.now()

        ts2 = datetime.now()
        picam2.stop_recording()
        print('Segment start time:', ts1.strftime('%H:%M:%S.%f'))
        print('Segment end time:', ts2.strftime('%H:%M:%S.%f'))
        ts1 = ts2
        segment += 1
    led.blink(on_time=1, off_time=1, on_color=(1,0,0), n=3) #visually indicate OFF status
    arec = False
    vrec = False
    print('<'*20,'A'*10,'V'*10)
    
    print('Audio recording finished: ' + repr(afilename))
    print('Video recording finished: ' + repr(vfilename))
 

recording = False
arec = False
vrec = False
shutdown_initiated = False
dt = timedelta(minutes=segment_length)


logging.basicConfig(filename='rec.log', level=logging.INFO)
logging.info('************************************************')
#consider adding break here so scripts don't conflict with one another if picamera already in use...


try:
    led = RGBLED(red=12, green=13, blue=19)
    picam2 = Picamera2()
    vconfig = picam2.create_video_configuration(main={"size": (resolution[0], resolution[1])}, controls={"FrameRate": framerate})
    picam2.configure(vconfig)
    encoder = H264Encoder()
    led.blink(on_time=.3, off_time=.2, on_color=(0,1,0), n=3) #visually indicate ON status
    print('Press button to start recording audio & video')
    button.when_released = button_press
    button.when_held = button_hold
    print('Press button again to stop recording')
    print('Hold button for %d seconds to end program and shutdown RPi' %3)
    
    time.sleep(1)
    print('LED indicator starting up:\n')
    print('\tRed = state')
    print('\tGreen = audio')
    print('\tBlue = video')
    print('\tYellow = state + audio')
    print('\tMagenta = state + video')
    print('\tCyan = audio + video')
    print('\tWhite = state + audio + video')
        
    while True:
        led.blink(on_time=.5, off_time=2.5, on_color=(.5*recording,.5*arec,.5*vrec), n=1, background=False)
        #time.sleep(3)
    #pause()
except KeyboardInterrupt:
    print('\n PROGRAM CANCELED')
    logging.info('\n Program Canceled.')
    #GPIO.cleanup()


