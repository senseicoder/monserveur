FROM monsrv_base
MAINTAINER Cédric Girard "c.girard@epiconcept.fr"

#RUN apt-get -y install apache2 php5 php5-cli php5-mysql php5-curl
#RUN mkdir /var/cedricconf

VOLUME /var/log/apache2
VOLUME /var/cedricconf
EXPOSE 80
CMD ["/usr/sbin/apache2ctl","-DFOREGROUND"]
