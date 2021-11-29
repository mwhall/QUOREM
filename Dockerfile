# syntax=docker/dockerfile:1
FROM ubuntu:impish
ENV PYTHONUNBUFFERED=1
WORKDIR /code
#COPY required config files first
COPY requirements.txt /code/
COPY scripts/qiime2/qiime2-2021.8-py38-linux-conda.yml /code/

####SYSTEM UPDATES####

#tzdata included as workaround so it doesn't hang on an update
#We need this even if we don't have apache2 running in the Docker yet
#Since mod_wsgi from requirements.txt requires apxs command
#If we remove mod_wsgi then we'd need to maintain two requirements.txt files
RUN apt-get -qq update && DEBIAN_FRONTEND="noninteractive" apt-get install --yes tzdata 
#apache2 apache2-dev

####INSTALL MINICONDA AND QIIME2####
RUN apt-get install --yes gcc-multilib g++-multilib curl graphviz
RUN curl -LO "http://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh"
RUN bash Miniconda3-latest-Linux-x86_64.sh -p /miniconda -b
RUN rm Miniconda3-latest-Linux-x86_64.sh
ENV PATH=/miniconda/bin:${PATH}
RUN conda update -y conda
RUN conda create --name quorem python=3.8.10
#This is the way to run a conda command when you can't activate, which we can't
#seem to from in here at build time, so this activates RUN commands that follow
# see: https://pythonspeed.com/articles/activate-conda-dockerfile/
SHELL ["conda", "run", "-n", "quorem", "/bin/bash", "-c"]
RUN conda env update --file qiime2-2021.8-py38-linux-conda.yml
RUN pip install -r requirements.txt
#Using VOLUME here causes timeouts with http on Django image
COPY . /code/
