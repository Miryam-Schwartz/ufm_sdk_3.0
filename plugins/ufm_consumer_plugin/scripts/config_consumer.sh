#!/bin/bash

# Update UFM consumer gv.cfg file. Set in section [Multisubnet]
# values for multisubnet_enabled = true and 
# multisubnet_role = consumer
. /opt/ufm/scripts/common

sqlite_conf=/config/sqlite
sqlite_target=/opt/ufm/files/sqlite
log_dir=/log
auth_log_file_path=/opt/ufm/files/log/authentication_service.log
ufm_media_original_path=/opt/ufm/media
consumer_media_path=/data/media

keep_config_file()
{
# verify that after plugin restart configuration file will be percistent
# and symbolic link will exist for config file in correct location
    conf_file_path=$1
    conf_file_name=$(basename $conf_file_path)
    target_dir=/config
    target_file_path="${target_dir}/${conf_file_name}"

    if [ ! -f ${target_file_path} ]; then
        if [ -f ${conf_file_path} ]; then
            mv ${conf_file_path} ${target_dir}
            ln -s ${target_file_path} ${conf_file_path}
        else
            echo "UFM file ${conf_file_path} not found"
            exit 1
        fi
    else # file exist, but need to check if link exist
        if [ -f ${conf_file_path} ] && [ ! -L ${conf_file_path} ]; then
            # The file is not a symbolic link
            rm -f ${conf_file_path}
            ln -s ${target_file_path} ${conf_file_path}
        fi
    fi
    chown -R ufmapp:ufmapp ${target_file_path} ${conf_file_path}
}

#
UpdCfg /opt/ufm/files/conf/gv.cfg Multisubnet multisubnet_enabled true
#
UpdCfg /opt/ufm/files/conf/gv.cfg Multisubnet multisubnet_role consumer

# Set correct port number for REST port (instead 8000)
#port_str=`cat /config/ufm_consumer_httpd_proxy.conf` ; port_value=`echo ${port_str#*=}`
if [ -f /ufm_consumer_plugin.conf ]; then
    config_file="/ufm_consumer_plugin.conf"
else
    config_file="/config/ufm_consumer_plugin.conf"
fi
port_value=`GetCfg $config_file common port_number`
# update in gv.cfg with port to listen 8997
if [ -z $port_value ]; then
    port_value="8997"
fi
UpdCfg /opt/ufm/files/conf/gv.cfg Server rest_port $port_value
UpdCfg /opt/ufm/files/conf/gv.cfg Server osm_traps_listening_port 8088
UpdCfg /opt/ufm/files/conf/gv.cfg UFMAgent default_ufma_port 6366
UpdCfg /opt/ufm/files/conf/gv.cfg Logging syslog_addr /dev/consumer_log
# Update authentication server configuration
# read the new auth service port from ufm_consumer_plugin.conf
auth_service_port=`GetCfg $config_file common auth_service_port`
UpdCfg /opt/ufm/files/conf/gv.cfg AuthService auth_service_port $auth_service_port
# update apache configuration
ssl_apache_port=`GetCfg $config_file common ssl_apache_port`
apache_port=`GetCfg $config_file common apache_port`
sed -i -e "s/Listen 443/Listen $ssl_apache_port/g" -e "s/Listen 80/Listen $apache_port/g" /etc/apache2/ports.conf
sed -i "s/VirtualHost _default_:443/VirtualHost _default_:$ssl_apache_port/g" /etc/apache2/sites-available/default-ssl.conf
sed -i "s/VirtualHost \*:80/VirtualHost \*:$apache_port/g" /etc/apache2/sites-available/000-default.conf
sed -i "s/APACHE_PORT/$ssl_apache_port/g" /config/ufm_consumer_ui_conf.json
# TODO: sqlite does not work of some reason with db file defined as synbolic link
# need to investigate: 
# 1. If UFM consumer should keep some data in database to be persistent
# 2. If yes - how to manage sqlight to work with db which is link pointing to another file


[ ! -f /opt/ufm/files/conf/ufm_providers_credentials.cfg ] &&  echo "[Credentials]" > /opt/ufm/files/conf/ufm_providers_credentials.cfg 
#for conf_file2keep in /opt/ufm/files/conf/gv.cfg /opt/ufm/files/sqlite/gv.db /opt/ufm/files/conf/ufm_providers_credentials.cfg;
for conf_file2keep in /opt/ufm/files/conf/gv.cfg /opt/ufm/files/conf/ufm_providers_credentials.cfg;
    do
         keep_config_file $conf_file2keep
    done

# special treatment for sqlite database. gv.db file should be percistent and for this purpose
# it is physically located on hosting server location and created a runtime link so it will be
# accessable from the plugin.
if [ ! -d ${sqlite_conf} ]; then
   # run first time
   if [ -d ${sqlite_target} ] && [ ! -L ${sqlite_target} ]; then
       mv ${sqlite_target} ${sqlite_conf}
       [ $? -ne 0 ] && echo "Failed to move ${sqlite_target} to ${sqlite_conf}" && exit 1
   else
       echo "Failed to move sql database files ${sqlite_target} to ${sqlite_conf directory}"
       exit 1
   fi
   # create symbolic link
   if [ -d ${sqlite_conf} ]; then
       ln -s ${sqlite_conf} ${sqlite_target}
       [ $? -ne 0 ] && echo "Failed to create symbolic link ${sqlite_conf} ${sqlite_target}" && exit 1
   fi
else
   # dir already exist from first run: rm orig and create symbolic link
   [ -d ${sqlite_target} ] && [ ! -L ${sqlite_target} ] && rm -rf ${sqlite_target}
   if [ ! -L ${sqlite_target} ]; then
       ln -s ${sqlite_conf} ${sqlite_target}
       [ $? -ne 0 ] && echo "Failed to create symbolic link ${sqlite_conf} ${sqlite_target} exist flow" && exit 1
   fi
fi
# special treatment for /opt/ufm/files/log/authentication_service.log file as it is created
# by ufm start as root user and on some setups remain with root permissions, so ufm with ufmapp user
# failed to write into that file. So create it if not exist
if [ ! -f ${auth_log_file_path} ]; then
    touch ${auth_log_file_path}
    chown ufmapp:ufmapp ${auth_log_file_path}
fi

chown -R ufmapp:ufmapp ${sqlite_target} ${sqlite_conf} ${log_dir}

# media directory of the UFM consumer should be shared with the host
# it will be served by the Host's apache, it should be accessible via the host
# /data default shared volume with the host's dir /opt/ufm/ufm_plugins_data/ufm_consumer/
if [ ! -f ${consumer_media_path} ]; then
    cp -r ${ufm_media_original_path} ${consumer_media_path}
fi
# update href base in the index.html of the UFM UI
sed -i "s/ufm_web/ufm_consumer_web/g" ${consumer_media_path}/index.html

echo "Consumer configuration completed successfully."
exit 0
