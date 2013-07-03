sudo apt-add-repository ppa:webupd8team/java
sudo apt-get update
sudo apt-get -y install unzip zip
sudo apt-get clean && sudo apt-get update
echo debconf shared/accepted-oracle-license-v1-1 select true | sudo debconf-set-selections
echo debconf shared/accepted-oracle-license-v1-1 seen true | sudo debconf-set-selections
sudo apt-get -y install oracle-java7-installer