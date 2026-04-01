## ssh into the server

ssh -i "novi.pem" ubuntu@ec2-54-161-95-50.compute-1.amazonaws.com

<!-- To ssh you need to have the private key file in your local machine. File name : summary-quiz-api-key_pair.pem -->

## show all running processes

ps xw

<!-- output should look like this 
  PID    TTY      STAT   TIME  COMMAND
 .....
 936157   ?        Sl   103:15 /home/ubuntu/.venv/bin/python3 /home/ubuntu/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 5000
 .....

You have to kill the existing running server 
-->

## kill a process or the server process

kill <PID>

<!-- should look like this 
[ubuntu@ip-172-31-10-169 ~]$ kill 936157
-->

## Now use ls to check the files and folders in the current directory

ls

## Command to show hidden files

ls -la

<!-- Output should look like this
Test         app.log      create_tables.sql  main.py              post_processing.py  prompt.py         summary-quiz-api-key_pair.pem
__pycache__  commands.md  logs.txt           notes_processing.py  pre_processing.py   requirements.txt  utils.py
 -->

## Remove the folder [optional]

sudo rm -rf <folder> 

# add the folder name inplace of <folder>

<!-- Once everything is deleted, you can clone the repository again -->

## Clone the repository [Not recommended Method]

git clone <url>

<!-- Output should look like this 
Cloning into 'CVOChat'...
remote: Enumerating objects: 10, done.
remote: Counting objects: 100% (10/10), done.
remote: Compressing objects: 100% (10/10), done.
remote: Total 10 (delta 0), reused 0 (delta 0), pack-reused 0
Unpacking objects: 100% (10/10), done.
Checking connectivity... done.
 -->

## OR you can copy the files from the local machine to the server

<!-- To do this you should need to be in the same directory that you want to copy the files to servers Ex: ~/CVOChat/chatbot-redis-backend/MM2 -->

scp -r -i "novi.pem" ./MM2 ubuntu@ec2-54-161-95-50.compute-1.amazonaws.com:~/

<!-- This will copy all the files and folders from the local machine to the server -->

## Now to run the server create the virtual environment and install the requirements

uv venv
source .venv/bin/activate

<!-- This will create the virtual environment and activate it -->

## To Deactivate the virtual environment [optional]

deactivate

## To install a package into the virtual environment:

uv pip install -r requirements.txt

<!-- This will install all the required packages -->

## To run the server in background with the output logs in file

nohup uvicorn main:app --host 0.0.0.0 --port 5000  > logs.txt

<!-- 
This will run the server in background and redirect the output to a file 
After the server is running, you can check the logs.txt file to see the output 

Check the APIs is working or Not
If it is working you can close the terminal and continue 

If it is not working, you can check the logs.txt file for the error
-->


## To download log file for debug
scp -i "novi.pem" ubuntu@ec2-54-161-95-50.compute-1.amazonaws.com:/home/ubuntu/MM2/logs.txt ~/Downloads/