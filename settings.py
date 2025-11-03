server = '10.231.31.195'
port = 5555

WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720
FPS = 60
SPRITE_SIZE = 64
# Number of players the server should accept/expect. First player (index 0)
# will be the seeker, all other connected players will be hidders.
# Change this to allow more players (client code may need updates to fully
# support more than 2 players).
NUM_PLAYERS = 2

# UDP discovery port for LAN server discovery (client will broadcast here,
# server will respond with its reachable IP/port). Default is port+1.
DISCOVERY_PORT = 5556

# Local TCP control port for administrative commands (shutdown). Default is port+2.
CONTROL_PORT = 5557