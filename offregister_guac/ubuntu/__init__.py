from sys import modules

from offregister_fab_utils.fs import cmd_avail
from pkg_resources import resource_filename
from os import path

from fabric.context_managers import cd
from fabric.contrib.files import append, upload_template, exists
from fabric.operations import run, sudo

from offregister_guac import get_logger
from offregister_fab_utils.apt import apt_depends

PKG_NAME = modules[__name__].__name__.partition(".")[0]
logger = get_logger(modules[__name__].__name__)


def install0(*args, **kwargs):
    install_deps()
    install_guac_server()
    install_guac_client()


def configure_tomcat1(*args, **kwargs):
    CATALINA_HOME = run("echo -n $CATALINA_HOME")
    tomcat_users_local_filepath = kwargs.get(
        "tomcat-users.xml",
        resource_filename(PKG_NAME, path.join("tomcat_conf", "tomcat-users.xml")),
    )
    upload_template(
        tomcat_users_local_filepath,
        "{CATALINA_HOME}/conf/tomcat-users.xml".format(CATALINA_HOME=CATALINA_HOME),
        context={
            "ADMIN_USERNAME": kwargs.get("ADMIN_USERNAME", "admin"),
            "ADMIN_PASSWORD": kwargs["ADMIN_PASSWORD"],
        },
        use_sudo=True,
    )

    with cd(CATALINA_HOME):
        """
        dae = 'commons-daemon-native'
        sudo('tar xf {dae}.tar.gz -C {dae} --strip-components 1'.format(dae=dae))
        with cd(dae):
            sudo('./configure')
            sudo('make')
            sudo('cp jsvc ../..')
        """
        if run("id -u tomcat", warn_only=True, quiet=True).failed:
            sudo("groupadd tomcat")
            sudo(
                "useradd -s /bin/false -g tomcat -d {CATALINA_HOME} tomcat".format(
                    CATALINA_HOME=CATALINA_HOME
                )
            )
        sudo("chgrp -R tomcat {CATALINA_HOME}".format(CATALINA_HOME=CATALINA_HOME))
        sudo("chmod -R g+r conf")
        sudo("chmod g+x conf")
        sudo("chown -R tomcat webapps/ work/ temp/ logs/")

        tomcat_service_local_filepath = kwargs.get(
            "tomcat.service",
            resource_filename(PKG_NAME, path.join("_data", "tomcat.service")),
        )
        upload_template(
            tomcat_service_local_filepath,
            "/etc/systemd/system/tomcat.service",
            context=dict(CATALINA_HOME=CATALINA_HOME),
            use_sudo=True,
        )
        return sudo("systemctl daemon-reload")


def serve2(*args, **kwargs):
    sudo("systemctl start tomcat")
    return sudo("/etc/init.d/guacd start")


def install_deps():
    # sudo('add-apt-repository ppa:mc3man/trusty-media')
    apt_depends(
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
    sudo(
        "update-alternatives --install /usr/bin/java java /usr/lib/jvm/java-8-openjdk-amd64/jre/bin/java 1"
    )
    sudo(
        "update-alternatives --install /usr/bin/javac javac /usr/lib/jvm/java-8-openjdk-amd64/bin/javac 1"
    )

    sudo("mkdir -p ~/Downloads")
    curr_ug = run("echo -n $USER:$GROUP", quiet=True)
    sudo("chown -R {curr_ug} ~/Downloads".format(curr_ug=curr_ug))
    with cd("Downloads"):
        libjpeg = "libjpeg-turbo-official_1.5.2_amd64.deb"
        if not exists(libjpeg):
            run(
                "curl -L 'https://downloads.sourceforge.net/project/libjpeg-turbo/{ver}/{pkg}' -o '{pkg}'".format(
                    pkg=libjpeg, ver=libjpeg.rpartition("_")[0].partition("_")[2]
                )
            )
            sudo("dpkg -i {pkg}".format(pkg=libjpeg))

        zlib = "zlib-1.2.11"
        if not exists(zlib):
            run("curl -OL http://www.zlib.net/{pkg}.tar.gz".format(pkg=zlib))
            run("tar xf {pkg}.tar.gz".format(pkg=zlib))
            with cd(zlib):
                run("./configure")
                run("make")
                sudo("make install")

        libvnc = "LibVNCServer-0.9.11"
        if not exists("{pkg}.tar.gz".format(pkg=libvnc)):
            run(
                "curl -OL https://github.com/LibVNC/libvncserver/archive/{pkg}.tar.gz".format(
                    pkg=libvnc
                )
            )
            run("tar xf {pkg}.tar.gz".format(pkg=libvnc))
            with cd("libvncserver-{pkg}".format(pkg=libvnc)):
                run("mkdir build")
                with cd("build"):
                    run("cmake ..")
                    run("cmake --build .")
                    sudo("make install")

        """freerdp = '2.0.0-rc0'
        run('curl -OL https://github.com/FreeRDP/FreeRDP/archive/{pkg}.tar.gz'.format(pkg=freerdp))
        run('tar xf {pkg}.tar.gz'.format(pkg=freerdp))
        with cd('FreeRDP-{pkg}'.format(pkg=freerdp)):
            run('rm -rf build')
            run('mkdir build')
            with cd('build'):
                run('cmake -DCMAKE_BUILD_TYPE=Debug -DWITH_SSE2=ON ..')
                run('make')
                sudo('make install')
                sudo('mkdir -p /etc/ld.so.conf.d')
                append('/etc/ld.so.conf.d/freerdp.conf', '/usr/local/lib/freerdp', use_sudo=True)
                sudo('ldconfig')"""

        libtelnet = "libtelnet-master"
        if not exists(libtelnet):
            run(
                "curl -L https://github.com/seanmiddleditch/libtelnet/archive/master.tar.gz -o {pkg}.tar.gz".format(
                    pkg=libtelnet
                )
            )
            run("tar xf {pkg}.tar.gz".format(pkg=libtelnet))
            with cd(libtelnet):
                run("autoreconf -fi")
                run(
                    'zlib_CFLAGS="-DHAVE_ZLIB=1" zlib_LIBS="-lz" ./configure --disable-util'
                )
                run("make")
                sudo("make install")
                sudo("ldconfig")

        if not cmd_avail("ffmpeg"):
            ffmpeg = "ffmpeg-3.3.4"
            run("curl -OL http://ffmpeg.org/releases/{pkg}.tar.bz2".format(pkg=ffmpeg))
            run("tar xf {pkg}.tar.bz2".format(pkg=ffmpeg))
            with cd(ffmpeg):
                run("./configure")
                run("make")
                sudo("make install")

        CATALINA_HOME = "/opt/javalibs/tomcat9"
        if not exists(CATALINA_HOME):
            sudo("mkdir -p {CATALINA_HOME}".format(CATALINA_HOME=CATALINA_HOME))
            append(
                "/etc/environment",
                "export CATALINA_HOME='{CATALINA_HOME}'".format(
                    CATALINA_HOME=CATALINA_HOME
                ),
                use_sudo=True,
            )
            tomcat = "apache-tomcat-9.0.1"
            tomcat_ver = tomcat.rpartition("-")[2]
            run(
                "curl -OL http://mirror.intergrid.com.au/apache/tomcat/tomcat-{ver[0]}/v{ver}/bin/{pkg}.tar.gz".format(
                    pkg=tomcat, ver=tomcat_ver
                )
            )
            sudo(
                "tar xf {pkg}.tar.gz -C {CATALINA_HOME} --strip-components=1".format(
                    pkg=tomcat, CATALINA_HOME=CATALINA_HOME
                )
            )

    return "installed dependencies"


def install_guac_server():
    if cmd_avail("guacenc"):
        return "Apache Guacamole server already installed"

    with cd("Downloads"):
        guac = "guacamole-server-0.9.13-incubating"
        run(
            "curl -OL 'http://apache.org/dyn/closer.cgi?action=download&filename=incubator/guacamole/0.9.13-incubating/source/{pkg}.tar.gz'".format(
                pkg=guac
            )
        )
        run("tar xf {pkg}.tar.gz".format(pkg=guac))
        with cd(guac):
            run("autoreconf -fi")
            run("./configure --with-init-dir=/etc/init.d")
            run("make")
            sudo("make install")
            sudo("ldconfig")

    return "installed Apache Guacamole server"


def install_guac_client():
    with cd("Downloads"):
        if not cmd_avail("mvn"):
            maven = "apache-maven-3.5.0-bin"
            run(
                "curl -OL http://apache.melbourneitmirror.net/maven/maven-{ver[0]}/{ver}/binaries/{pkg}.tar.gz".format(
                    pkg=maven, ver=maven.rpartition("-")[0].rpartition("-")[2]
                )
            )
            d = "/opt/javalibs/maven"
            sudo("mkdir -p {d}".format(d=d))
            sudo(
                "tar xf {pkg}.tar.gz -C {d} --strip-components=1".format(pkg=maven, d=d)
            )
            with cd(d):
                sudo(
                    "ln -s '{d}/bin/mvn' '/usr/local/bin/$b'".format(d=d),
                    shell_escape=False,
                )
        guac_client = "0.9.13-incubating"
        if not exists("{pkg}.tar.gz".format(pkg=guac_client)):
            run(
                "curl -OL https://github.com/apache/incubator-guacamole-client/archive/{pkg}.tar.gz".format(
                    pkg=guac_client
                )
            )
            run("tar xf {pkg}.tar.gz".format(pkg=guac_client))
        with cd("incubator-guacamole-client-{pkg}".format(pkg=guac_client)):
            war = "guacamole/target/guacamole-0.9.13-incubating.war"
            if not exists(war):
                run("mvn package")
            sudo("cp {war} $CATALINA_HOME/webapps".format(war=war))
