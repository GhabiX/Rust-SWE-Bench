FROM sweagent/swe-agent:latest

WORKDIR /root
# change ubuntu resource
RUN sed -i 's|http://archive.ubuntu.com/ubuntu/|http://mirrors.aliyun.com/ubuntu/|g' /etc/apt/sources.list && \
    sed -i 's|http://security.ubuntu.com/ubuntu/|http://mirrors.aliyun.com/ubuntu/|g' /etc/apt/sources.list && \
    apt-get update --allow-insecure-repositories && \
    apt-get install -y vim --allow-unauthenticated

# install maven
RUN wget https://dlcdn.apache.org/maven/maven-3/3.9.8/binaries/apache-maven-3.9.8-bin.tar.gz && \
    tar -zxvf apache-maven-3.9.8-bin.tar.gz && \
    mv apache-maven-3.9.8 /opt/maven 
COPY docker/assets/settings.xml /opt/maven/conf/settings.xml
COPY docker/assets/init.gradle /root/.gradle/init.gradle

ENV MAVEN_HOME=/opt/maven
ENV PATH=$MAVEN_HOME/bin:$PATH
