FROM monsrv_apache
MAINTAINER Cédric Girard "c.girard@epiconcept.fr"

#RUN rm -f /etc/apt/apt.conf.d/no-cache
#RUN echo 'Acquire::http { Proxy "http://172.17.0.1:3142"; };' >> /etc/apt/apt.conf.d/01proxy

RUN apt-get --yes install git
RUN git clone https://tt-rss.org/git/tt-rss.git
RUN rm -r /var/www/html
RUN mv tt-rss /var/www/html

EXPOSE 80
CMD ["/usr/sbin/apache2ctl","-DFOREGROUND"]
