FROM agentshed/requirements
MAINTAINER John Chilton <jmchilton@gmail.com>

ENV MYSQL_MAJOR=5.6

# Pre-install a bunch of packages to speed up ansible steps.
RUN apt-get update -y && apt-get install -y software-properties-common curl && \
    apt-add-repository -y ppa:ansible/ansible && \
    curl -s https://deb.nodesource.com/gpgkey/nodesource.gpg.key | apt-key add - && \
    echo 'deb https://deb.nodesource.com/node trusty main' > /etc/apt/sources.list.d/nodesource.list && \
    apt-key adv --keyserver pool.sks-keyservers.net --recv-keys A4A9406876FCBD3C456770C88C718D3B5072E1F5 && \
    echo "deb http://repo.mysql.com/apt/ubuntu/ trusty mysql-${MYSQL_MAJOR}" > /etc/apt/sources.list.d/mysql.list && \
    { \
		echo mysql-community-server mysql-community-server/data-dir select ''; \
		echo mysql-community-server mysql-community-server/root-pass password ''; \
		echo mysql-community-server mysql-community-server/re-root-pass password ''; \
		echo mysql-community-server mysql-community-server/remove-test-db select false; \
	} | debconf-set-selections && \
    apt-get update -y && \
    apt-get install -y libpq-dev postgresql postgresql-client postgresql-plpython-9.3 \
            ansible postgresql-server-dev-9.3 wget mysql-server="${MYSQL_MAJOR}"* \
            slurm-llnl libmunge-dev slurm-drmaa-dev ant atop axel bioperl cmake curl \
            g++ gcc gfortran git-core htop iftop iotop ipython libffi-dev liblapack-dev \
            libncurses5-dev libopenblas-dev libpam0g-dev libpq-dev libsparsehash-dev make \
            mercurial nginx-extras nmon patch postgresql postgresql \
            postgresql-client postgresql-plpython-9.3 python-boto python-dev \
            python-prettytable python-psycopg2 python-virtualenv python-pip \
            postgresql-server-dev-9.3 rsync slurm-drmaa-dev supervisor swig sysstat unzip \
            wget zlib1g-dev nodejs && \
    npm install -g grunt-contrib-qunit grunt grunt-cli casperjs phantomjs && \
    apt-get autoremove -y && apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

RUN mkdir -p /tmp/ansible && \
    mkdir -p /opt/galaxy/db && \
    chown -R postgres:postgres /opt/galaxy/db && \
    sed -Ei 's/^(bind-address|log)/#&/' /etc/mysql/my.cnf

ADD start_mysql.sh /opt/galaxy/start_mysql.sh
ADD ansible_vars.yml /tmp/ansible/ansible_vars.yml
ADD provision.yml /tmp/ansible/provision.yml

ENV GALAXY_ROOT=/galaxy

RUN mkdir /etc/galaxy && cd /tmp/ansible && mkdir roles && \
    mkdir roles/galaxyprojectdotorg.galaxy-os && \
    wget --quiet -O- https://github.com/galaxyproject/ansible-galaxy-os/archive/master.tar.gz | tar -xzf- --strip-components=1 -C roles/galaxyprojectdotorg.galaxy-os && \
    mkdir roles/galaxyprojectdotorg.cloudman-database && \
    wget --quiet -O- https://github.com/galaxyproject/ansible-cloudman-database/archive/master.tar.gz | tar -xzf- --strip-components=1 -C roles/galaxyprojectdotorg.cloudman-database && \
    mkdir roles/galaxyprojectdotorg.galaxy && \
    wget --quiet -O- https://github.com/galaxyproject/ansible-galaxy/archive/master.tar.gz | tar -xzf- --strip-components=1 -C roles/galaxyprojectdotorg.galaxy && \
    mkdir roles/galaxyprojectdotorg.galaxy-extras && \
    wget --quiet -O- https://github.com/galaxyproject/ansible-galaxy-extras/archive/dynamic_uwsgi_config.tar.gz | tar -xzf- --strip-components=1 -C roles/galaxyprojectdotorg.galaxy-extras && \
    mkdir roles/galaxyprojectdotorg.galaxy-agentshed && \
    wget --quiet -O- https://github.com/galaxyproject/ansible-galaxy-agentshed/archive/master.tar.gz | tar -xzf- --strip-components=1 -C roles/galaxyprojectdotorg.galaxy-agentshed && \
    ANSIBLE_FORCE_COLOR=1 PYTHONUNBUFFERED=1 ansible-playbook /tmp/ansible/provision.yml --tags=image -c local -e "@ansible_vars.yml" && \
    ANSIBLE_FORCE_COLOR=1 PYTHONUNBUFFERED=1 ansible-playbook /tmp/ansible/provision.yml --tags=database -c local -e "@ansible_vars.yml" && \
    ANSIBLE_FORCE_COLOR=1 PYTHONUNBUFFERED=1 ansible-playbook /tmp/ansible/provision.yml --tags=galaxy -c local -e "@ansible_vars.yml" && \
    ANSIBLE_FORCE_COLOR=1 PYTHONUNBUFFERED=1 ansible-playbook /tmp/ansible/provision.yml --tags=agentshed -c local -e "@ansible_vars.yml" && \
    apt-get autoremove -y && apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

RUN cd $GALAXY_ROOT && \
    echo "Prepopulating postgres database" && \
    su -c '/usr/lib/postgresql/9.3/bin/pg_ctl -o "-F" start -D /opt/galaxy/db' postgres && \
    sleep 3 && \
    GALAXY_CONFIG_DATABASE_CONNECTION="postgresql://root@localhost:5930/galaxy" sh create_db.sh && \
    echo "Prepopulating sqlite database" && \
    GALAXY_CONFIG_DATABASE_CONNECTION="sqlite:////opt/galaxy/galaxy.sqlite" sh create_db.sh && \
    sh /opt/galaxy/start_mysql.sh && \
    echo "Prepopulating mysql database" && \
    GALAXY_CONFIG_DATABASE_CONNECTION="mysql://galaxy:galaxy@localhost/galaxy?unix_socket=/var/run/mysqld/mysqld.sock" sh create_db.sh && \
    echo "Prepopulating agentshed postgres database" && \
    su -c '/usr/lib/postgresql/9.3/bin/pg_ctl -o "-F" start -D /opt/galaxy/db' postgres && \
    GALAXY_CONFIG_DATABASE_CONNECTION="postgresql://root@localhost:5930/agentshed" sh create_db.sh agent_shed && \
    echo "Prepopulating agentshed sqlite database" && \
    GALAXY_CONFIG_DATABASE_CONNECTION="sqlite:////opt/galaxy/agentshed.sqlite" sh create_db.sh agent_shed && \
    sh /opt/galaxy/start_mysql.sh && \
    echo "Prepopulating agentshed mysql database" && \
    GALAXY_CONFIG_DATABASE_CONNECTION="mysql://galaxy:galaxy@localhost/agentshed?unix_socket=/var/run/mysqld/mysqld.sock" sh create_db.sh agent_shed

# bcfagents for Galaxy.
RUN mkdir -p /tmp/install && \
    cd /tmp/install && \
    wget https://github.com/samagents/bcfagents/releases/download/1.2/bcfagents-1.2.tar.bz2 && \
    tar xvjf bcfagents-1.2.tar.bz2 && \
    cd bcfagents-1.2 && \
    make && \
    make install && \
    cd && rm -rf /tmp/install
    
ADD run_test_wrapper.sh /usr/local/bin/run_test_wrapper.sh

EXPOSE :9009
EXPOSE :8080
EXPOSE :80
ENTRYPOINT ["/bin/bash", "/usr/local/bin/run_test_wrapper.sh"]
