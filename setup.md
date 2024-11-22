- **Initial PVE setup**

```shell
# config.env
USER=***
EMAIL="******"
NAME="*****"
```

```shell
#!/bin/bash

# Load configuration from a file
source ./config.env

# Install required packages
echo "Updating packages and installing dependencies..."
apt update && apt install -y ansible acl apt-transport-https autoconf autopoint automake \
ca-certificates chrony curl dnsutils dstat fio git gnupg gnupg-agent htop jq libtool \
lsb-release ncdu net-tools nfs-common parted pkg-config psmisc pv python3 python3-dev \
python3-pip python3-virtualenv qemu-guest-agent rsync screen smartmontools \
software-properties-common sysstat sudo tmux traceroute tree ufw unison unzip \
vim wget zsh || { echo "Package installation failed"; exit 1; }

# Check if the system is a Proxmox VE host
if [[ ! -d /etc/pve ]]; then
    # Enable qemu-guest-agent service
    echo "Enabling QEMU Guest Agent service..."
    systemctl enable qemu-guest-agent && systemctl start qemu-guest-agent
    
    # Synchronize time using chrony
    echo "Configuring chrony for time synchronization..."
    systemctl enable chrony && systemctl start chrony
fi

# Check for required variables in config.env
if [[ -z "$USER" || -z "$EMAIL" || -z "$NAME" ]]; then
    echo "Missing required configuration. Please check config.env."
    exit 1
fi

# Prompt for password if not set in config.env
if [[ -z "$PASSWORD" ]]; then
    read -sp "Enter password for $USER: " PASSWORD
    echo
fi

# Validate email format
if ! [[ "$EMAIL" =~ ^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$ ]]; then
    echo "Invalid email address: $EMAIL"
    exit 1
fi

# Check if user already exists
if id "$USER" &>/dev/null; then
    echo "User $USER already exists."
else
    echo "Creating user $USER..."
    PASSWORD_HASH=$(openssl passwd -6 "$PASSWORD")
    useradd "$USER" -m -s /bin/zsh -p "$PASSWORD_HASH" || { echo "Failed to create user $USER"; exit 1; }
    
    # Add user to sudoers file securely
    echo "$USER ALL=(ALL) NOPASSWD:ALL" | EDITOR='tee -a' visudo -f /etc/sudoers.d/$USER
    chmod 440 /etc/sudoers.d/$USER
fi

# Configure Git user settings
echo "Configuring Git for user $USER..."
git config --global user.email "$EMAIL"
git config --global user.name "$NAME"

echo "Initial PVE setup completed successfully!"
```
