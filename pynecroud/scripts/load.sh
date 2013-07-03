WORLDNAME="{world_name}"
DEST=/srv/minecraft-server/$WORLDNAME
tar xvzf $WORLDNAME.tar.gz
[ -e $DEST ] && rm -rf $DEST
sudo mv $WORLDNAME $DEST
sudo chown -R minecraft $DEST
