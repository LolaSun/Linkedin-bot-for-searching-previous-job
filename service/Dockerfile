FROM python:3.8
COPY . /app
COPY requirements.txt /app/requirements.txt

# Adding Google Chrome to the repositories
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -
RUN sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list'

RUN apt-get update -y
RUN apt-get install -y python3-pip python3-dev build-essential google-chrome-stable
RUN pip3 install --upgrade pip
RUN pip3 install pyTelegramBotAPI
RUN pip3 install -r /app/requirements.txt
WORKDIR /app
EXPOSE 80
CMD ["python3", "start.py"]