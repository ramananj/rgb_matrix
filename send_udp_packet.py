import socket
import sys

# Server IP address and port
SERVER_IP = "192.168.86.39"  # Replace with your server's IP
SERVER_PORT = 50000

# Create a UDP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Get the message from the user (or a defined value)
message = "hi there"
data = message.encode('utf-8')

# Send the data
sock.sendto(data, (SERVER_IP, SERVER_PORT))

# Optional: Display a confirmation
print(f"Sent '{message}' to {SERVER_IP}:{SERVER_PORT}")

# Close the socket (optional, but good practice)
sock.close()