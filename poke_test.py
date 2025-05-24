import os
try:
    fd = os.open("/dev/pio0", os.O_RDWR)
    print("✅ Opened /dev/pio0 as fd", fd)
    os.close(fd)
except Exception as e:
    print("❌ Failed to open /dev/pio0:", e)
