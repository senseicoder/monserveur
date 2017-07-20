FROM debian:jessie
MAINTAINER Cédric Girard "c.girard@epiconcept.fr"

#RUN rm -f /etc/apt/apt.conf.d/no-cache
#RUN echo 'Acquire::http { Proxy "http://172.17.0.1:3142"; };' >> /etc/apt/apt.conf.d/01proxy

RUN apt-get update && apt-get upgrade -y && apt-get -y install vim tree curl less && apt-get clean