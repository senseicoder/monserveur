FROM mysql:5.7
MAINTAINER Cédric Girard "c.girard@epiconcept.fr"

RUN apt-get -y install mysql-server mysql-client

VOLUME /var/lib/mysql
EXPOSE 3306
CMD ["mysqld"]
