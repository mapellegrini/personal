alias e='emacs'
alias movie='cd /mnt/data3/movie'
alias tv='cd /mnt/data2/tv'
alias tv2='cd /mnt/data4/tv'
alias unsorted='cd /mnt/data2/unsorted'
alias kids='cd /mnt/data3/kids'
alias doc='cd /mnt/data3/documentaries'
alias docs='cd /mnt/data3/documentaries'
alias pics='cd /mnt/data/pictures/my_photos'
alias ytdl='yt-dlp -o "%(title)s.f%(format_id)s.%(ext)s"'
alias dur='exiftool -api LargeFileSupport=1 -j -Duration '

alias setperms='find . -type d -exec chmod 755 {} + && find . -type f -exec chmod 644 {} +'

alias findperms='find /mnt/data/personal_video \( -type f ! -perm 0644 -o -type d ! -perm 0755 \) -print; find /mnt/data/pictures/my_photos \( -type f ! -perm 0644 -o -type d ! -perm 0755 \) -print; find /mnt/data2/tv \( -type f ! -perm 0644 -o -type d ! -perm 0755 \) -print; find /mnt/data3/movie \( -type f ! -perm 0644 -o -type d ! -perm 0755 \) -print; find /mnt/data4/sports \( -type f ! -perm 0644 -o -type d ! -perm 0755 \) -print; find /mnt/data4/tv \( -type f ! -perm 0644 -o -type d ! -perm 0755 \) -print'

alias plexaccess='f(){ sudo -u plex test -r "$1" && echo "YES: plex can read $1" || echo "NO: plex cannot read $1"; }; f'