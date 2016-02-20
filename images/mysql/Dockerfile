FROM monsrv_base
MAINTAINER Cédric Girard "c.girard@epiconcept.fr"

RUN apt-get -y install mysql-server mysql-client

RUN mysql -e "create database ttrss"
RUN mysql -e "CREATE USER 'ttrss'@'%' IDENTIFIED BY 'ttrss';"
RUN mysql -e "GRANT USAGE ON*.*TO 'ttrss'@'%';"
RUN mysql -e "GRANT ALL PRIVILEGES ON ttrss.* TO 'ttrss'@'%';

VOLUME /var/lib/mysql
EXPOSE 3306
CMD ["mysqld"]
