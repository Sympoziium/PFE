ssh pi@192.168.10.1 //
cd PFE
git checkout Oli
git pull
sudo ~/PFE/zumi_prepare.sh fast
python3 main.py
