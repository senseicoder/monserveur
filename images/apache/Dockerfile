FROM ubuntu
MAINTAINER Cédric Girard "c.girard@epiconcept.fr"

#RUN rm -f /etc/apt/apt.conf.d/no-cache
#RUN echo 'Acquire::http { Proxy "http://172.17.0.1:3142"; };' >> /etc/apt/apt.conf.d/01proxy

RUN apt-get update
RUN apt-get upgrade -y
RUN apt-get -y install apache2 php5 vim tree php5-cli php5-mysql php5-curl curl less

EXPOSE 80
CMD ["/usr/sbin/apache2ctl","-DFOREGROUND"]
