import time, os
print("ravel is running on these gpus:", os.getenv("NVIDIA_VISIBLE_DEVICES"))
time.sleep(10)
print("hello from ravel")