sudo mkdir -p /srv/minecraft-server
sudo wget -O /srv/minecraft-server/minecraft_server.jar https://s3.amazonaws.com/MinecraftDownload/launcher/minecraft_server.jar
sudo adduser --system --no-create-home --home /srv/minecraft-server minecraft
sudo chown -R minecraft /srv/minecraft-server