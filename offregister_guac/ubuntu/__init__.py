from os import path
from sys import modules

from offregister_fab_utils.apt import apt_depends
from offregister_fab_utils.fs import cmd_avail
from patchwork.files import append, exists
from pkg_resources import resource_filename

from offregister_guac import get_logger

PKG_NAME = modules[__name__].__name__.partition(".")[0]
logger = get_logger(modules[__name__].__name__)


def install0(*args, **kwargs):
    install_deps()
    install_guac_server()
    install_guac_client()


def configure_tomcat1(*args, **kwargs):
    CATALINA_HOME = c.run("echo -n $CATALINA_HOME").stdout.rstrip()
    tomcat_users_local_filepath = kwargs.get(
        "tomcat-users.xml",
        resource_filename(PKG_NAME, path.join("tomcat_conf", "tomcat-users.xml")),
    )
    upload_template_fmt(
        c,
        tomcat_users_local_filepath,
        "{CATALINA_HOME}/conf/tomcat-users.xml".format(CATALINA_HOME=CATALINA_HOME),
        context={
            "ADMIN_USERNAME": kwargs.get("ADMIN_USERNAME", "admin"),
            "ADMIN_PASSWORD": kwargs["ADMIN_PASSWORD"],
        },
        use_sudo=True,
    )

    with c.cd(CATALINA_HOME):
        """
        dae = 'commons-daemon-native'
        c.sudo('tar xf {dae}.tar.gz -C {dae} --strip-components 1'.format(dae=dae))
        with c.cd(dae):
            c.sudo('./configure')
            c.sudo('make')
            c.sudo('cp jsvc ../..')
        """
        if c.run("id -u tomcat", warn=True, hide=True).exited != 0:
            c.sudo("groupadd tomcat")
            c.sudo(
                "useradd -s /bin/false -g tomcat -d {CATALINA_HOME} tomcat".format(
                    CATALINA_HOME=CATALINA_HOME
                )
            )
        c.sudo("chgrp -R tomcat {CATALINA_HOME}".format(CATALINA_HOME=CATALINA_HOME))
        c.sudo("chmod -R g+r conf")
        c.sudo("chmod g+x conf")
        c.sudo("chown -R tomcat webapps/ work/ temp/ logs/")

        tomcat_service_local_filepath = kwargs.get(
            "tomcat.service",
            resource_filename(PKG_NAME, path.join("_data", "tomcat.service")),
        )
        upload_template_fmt(
            c,
            tomcat_service_local_filepath,
            "/etc/systemd/system/tomcat.service",
            context=dict(CATALINA_HOME=CATALINA_HOME),
            use_sudo=True,
        )
        return c.sudo("systemctl daemon-reload")


def serve2(*args, **kwargs):
    c.sudo("systemctl start tomcat")
    return c.sudo("/etc/init.d/guacd start")


def install_deps():
    # c.sudo('add-apt-repository ppa:mc3man/trusty-media')
    apt_depends(
        c,
        "curl",
        # From  Guacamole
        "libcairo2-dev",  # 'libjpeg62-turbo-dev', 'libjpeg62-dev',
        "libpng12-dev",
        "libossp-uuid-dev",
        "libpango-1.0-0",
        "libpango1.0-dev",
        "libssh2-1",
        "libssh2-1-dev",
        "libpulse-dev",
        "libssl-dev",
        "libvorbis-dev",
        "libwebp-dev",
        "libfreerdp-dev",  # 'ffmpeg'
        "openjdk-8-jdk",  # <- client
        # From FreeRDP
        "build-essential",
        "git-core",
        "cmake",
        "xsltproc",
        "libssl-dev",
        "libx11-dev",
        "libxext-dev",
        "libxinerama-dev",
        "libxcursor-dev",
        "libxdamage-dev",
        "libxv-dev",
        "libxkbfile-dev",
        "libasound2-dev",
        "libcups2-dev",
        "libxml2",
        "libxml2-dev",
        "libxrandr-dev",
        "libgstreamer0.10-dev",
        "libgstreamer-plugins-base0.10-dev",
        "libxi-dev",
        "libgstreamer-plugins-base1.0-dev",
        "libavutil-dev",
        "libavcodec-dev",
        "libdirectfb-dev",
        # From libtelnet
        "autoconf",
        "libtool",
        "automake",
        # From ffmpeg
        "yasm",
    )
    c.sudo(
        "update-alternatives --install /usr/bin/java java /usr/lib/jvm/java-8-openjdk-amd64/jre/bin/java 1"
    )
    c.sudo(
        "update-alternatives --install /usr/bin/javac javac /usr/lib/jvm/java-8-openjdk-amd64/bin/javac 1"
    )

    c.sudo("mkdir -p ~/Downloads")
    curr_ug = c.run("echo -n $USER:$GROUP", hide=True).stdout.rstrip()
    c.sudo("chown -R {curr_ug} ~/Downloads".format(curr_ug=curr_ug))
    with c.cd("Downloads"):
        libjpeg = "libjpeg-turbo-official_1.5.2_amd64.deb"
        if not exists(c, runner=c.run, path=libjpeg):
            c.run(
                "curl -L 'https://downloads.sourceforge.net/project/libjpeg-turbo/{ver}/{pkg}' -o '{pkg}'".format(
                    pkg=libjpeg, ver=libjpeg.rpartition("_")[0].partition("_")[2]
                )
            )
            c.sudo("dpkg -i {pkg}".format(pkg=libjpeg))

        zlib = "zlib-1.2.11"
        if not exists(c, runner=c.run, path=zlib):
            c.run("curl -OL http://www.zlib.net/{pkg}.tar.gz".format(pkg=zlib))
            c.run("tar xf {pkg}.tar.gz".format(pkg=zlib))
            with c.cd(zlib):
                c.run("./configure")
                c.run("make")
                c.sudo("make install")

        libvnc = "LibVNCServer-0.9.11"
        if not exists(c, runner=c.run, path="{pkg}.tar.gz".format(pkg=libvnc)):
            c.run(
                "curl -OL https://github.com/LibVNC/libvncserver/archive/{pkg}.tar.gz".format(
                    pkg=libvnc
                )
            )
            c.run("tar xf {pkg}.tar.gz".format(pkg=libvnc))
            with c.cd("libvncserver-{pkg}".format(pkg=libvnc)):
                c.run("mkdir build")
                with c.cd("build"):
                    c.run("cmake ..")
                    c.run("cmake --build .")
                    c.sudo("make install")

        """freerdp = '2.0.0-rc0'
        c.run('curl -OL https://github.com/FreeRDP/FreeRDP/archive/{pkg}.tar.gz'.format(pkg=freerdp))
        c.run('tar xf {pkg}.tar.gz'.format(pkg=freerdp))
        with c.cd('FreeRDP-{pkg}'.format(pkg=freerdp)):
            c.run('rm -rf build')
            c.run('mkdir build')
            with c.cd('build'):
                c.run('cmake -DCMAKE_BUILD_TYPE=Debug -DWITH_SSE2=ON ..')
                c.run('make')
                c.sudo('make install')
                c.sudo('mkdir -p /etc/ld.so.conf.d')
                append(c, c.sudo, '/etc/ld.so.conf.d/freerdp.conf', '/usr/local/lib/freerdp')
                c.sudo('ldconfig')"""

        libtelnet = "libtelnet-master"
        if not exists(c, runner=c.run, path=libtelnet):
            c.run(
                "curl -L https://github.com/seanmiddleditch/libtelnet/archive/master.tar.gz -o {pkg}.tar.gz".format(
                    pkg=libtelnet
                )
            )
            c.run("tar xf {pkg}.tar.gz".format(pkg=libtelnet))
            with c.cd(libtelnet):
                c.run("autoreconf -fi")
                c.run(
                    'zlib_CFLAGS="-DHAVE_ZLIB=1" zlib_LIBS="-lz" ./configure --disable-util'
                )
                c.run("make")
                c.sudo("make install")
                c.sudo("ldconfig")

        if not cmd_avail(c, "ffmpeg"):
            ffmpeg = "ffmpeg-3.3.4"
            c.run(
                "curl -OL http://ffmpeg.org/releases/{pkg}.tar.bz2".format(pkg=ffmpeg)
            )
            c.run("tar xf {pkg}.tar.bz2".format(pkg=ffmpeg))
            with c.cd(ffmpeg):
                c.run("./configure")
                c.run("make")
                c.sudo("make install")

        CATALINA_HOME = "/opt/javalibs/tomcat9"
        if not exists(c, runner=c.run, path=CATALINA_HOME):
            c.sudo("mkdir -p {CATALINA_HOME}".format(CATALINA_HOME=CATALINA_HOME))
            append(
                c,
                c.sudo,
                "/etc/environment",
                "export CATALINA_HOME='{CATALINA_HOME}'".format(
                    CATALINA_HOME=CATALINA_HOME
                ),
            )
            tomcat = "apache-tomcat-9.0.1"
            tomcat_ver = tomcat.rpartition("-")[2]
            c.run(
                "curl -OL http://mirror.intergrid.com.au/apache/tomcat/tomcat-{ver[0]}/v{ver}/bin/{pkg}.tar.gz".format(
                    pkg=tomcat, ver=tomcat_ver
                )
            )
            c.sudo(
                "tar xf {pkg}.tar.gz -C {CATALINA_HOME} --strip-components=1".format(
                    pkg=tomcat, CATALINA_HOME=CATALINA_HOME
                )
            )

    return "installed dependencies"


def install_guac_server():
    if cmd_avail(c, "guacenc"):
        return "Apache Guacamole server already installed"

    with c.cd("Downloads"):
        guac = "guacamole-server-0.9.13-incubating"
        c.run(
            "curl -OL 'http://apache.org/dyn/closer.cgi?action=download&filename=incubator/guacamole/0.9.13-incubating/source/{pkg}.tar.gz'".format(
                pkg=guac
            )
        )
        c.run("tar xf {pkg}.tar.gz".format(pkg=guac))
        with c.cd(guac):
            c.run("autoreconf -fi")
            c.run("./configure --with-init-dir=/etc/init.d")
            c.run("make")
            c.sudo("make install")
            c.sudo("ldconfig")

    return "installed Apache Guacamole server"


def install_guac_client():
    with c.cd("Downloads"):
        if not cmd_avail(c, "mvn"):
            maven = "apache-maven-3.5.0-bin"
            c.run(
                "curl -OL http://apache.melbourneitmirror.net/maven/maven-{ver[0]}/{ver}/binaries/{pkg}.tar.gz".format(
                    pkg=maven, ver=maven.rpartition("-")[0].rpartition("-")[2]
                )
            )
            d = "/opt/javalibs/maven"
            c.sudo("mkdir -p {d}".format(d=d))
            c.sudo(
                "tar xf {pkg}.tar.gz -C {d} --strip-components=1".format(pkg=maven, d=d)
            )
            with c.cd(d):
                c.sudo("ln -s '{d}/bin/mvn' '/usr/local/bin/$b'".format(d=d))
        guac_client = "0.9.13-incubating"
        if not exists(c, runner=c.run, path="{pkg}.tar.gz".format(pkg=guac_client)):
            c.run(
                "curl -OL https://github.com/apache/incubator-guacamole-client/archive/{pkg}.tar.gz".format(
                    pkg=guac_client
                )
            )
            c.run("tar xf {pkg}.tar.gz".format(pkg=guac_client))
        with c.cd("incubator-guacamole-client-{pkg}".format(pkg=guac_client)):
            war = "guacamole/target/guacamole-0.9.13-incubating.war"
            if not exists(c, runner=c.run, path=war):
                c.run("mvn package")
            c.sudo("cp {war} $CATALINA_HOME/webapps".format(war=war))
