#!/bin/sh
# Pushtoo installer: https://github.com/tucktuckg00se/Pushtoo
#
#   curl -fsSL https://raw.githubusercontent.com/tucktuckg00se/Pushtoo/main/install.sh | sh
#   ./install.sh            (from a clone)
#   ./install.sh --help     (options, uninstalling)
#
# It asks before every step and recaps your answers before doing anything. It uses
# sudo only for system packages and the udev rule, and only if you say yes.

set -eu

REPO="tucktuckg00se/Pushtoo"
DEFAULT_REF="v0.1.0b1"
SERVICE="pushtoo.service"
RULE="50-pushtoo.rules"

ref="$DEFAULT_REF"
source_dir=""      # --from: install this checkout instead of downloading
assume_yes=0
uninstall=0
purge=0
skip_packages=0
skip_udev=0
skip_service=0
skip_start=0

usage() {
	cat <<'EOF'
Usage: install.sh [options]

Installs Pushtoo for your user, asking before each step:
  1. system packages Pushtoo needs to build (sudo)
  2. uv, the Python tool installer (if missing)
  3. Pushtoo itself, as the `pushtoo` command
  4. a udev rule so Pushtoo can use the Push display and Undo keys without root (sudo)
  5. membership of the "audio" group (sudo)
  6. starting Pushtoo automatically when you log in (a systemd user service)
  7. starting it now

Options:
  --yes            accept every default without asking
  --no-packages    skip installing system packages
  --no-udev        skip the udev rule and the audio group
  --no-service     don't set up the background service
  --no-start       set up the service but don't start it now
  --main           install the latest code (main) instead of the release
  --ref REF        install this tag, branch or commit
  --from DIR       install from a local checkout
  --uninstall      remove Pushtoo, its service and its udev rule (asks first)
  --purge          with --uninstall: also delete your profiles, themes and state
  -h, --help       this help
EOF
}

while [ $# -gt 0 ]; do
	case "$1" in
	--yes | -y) assume_yes=1 ;;
	--no-packages) skip_packages=1 ;;
	--no-udev) skip_udev=1 ;;
	--no-service) skip_service=1 ;;
	--no-start) skip_start=1 ;;
	--main) ref="main" ;;
	--ref) shift; ref="${1:?--ref needs a value}" ;;
	--from) shift; source_dir="${1:?--from needs a directory}" ;;
	--uninstall) uninstall=1 ;;
	--purge) purge=1 ;;
	-h | --help) usage; exit 0 ;;
	*) echo "Unknown option: $1 (see --help)" >&2; exit 2 ;;
	esac
	shift
done

# --- talking to the person running this ----------------------------------------

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
say() { printf '%s\n' "$*"; }
step() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }

# Answers come from the terminal even when this script arrives on stdin (curl | sh).
if [ "$assume_yes" -eq 0 ]; then
	if [ -r /dev/tty ] && (: </dev/tty) 2>/dev/null; then
		tty_in=/dev/tty
	else
		say "No terminal to ask questions on. Re-run with --yes to accept the defaults," >&2
		say "or with options such as --no-udev --no-service (see --help)." >&2
		exit 2
	fi
fi

# ask QUESTION DEFAULT(y|n) -> exit status 0 for yes
ask() {
	if [ "$assume_yes" -eq 1 ]; then
		[ "$2" = y ]
		return
	fi
	if [ "$2" = y ]; then hint="[Y/n]"; else hint="[y/N]"; fi
	while :; do
		printf '%s %s ' "$1" "$hint"
		read -r answer <"$tty_in" || answer=""
		case "$answer" in
		"") [ "$2" = y ]; return ;;
		[Yy]*) return 0 ;;
		[Nn]*) return 1 ;;
		esac
	done
}

have() { command -v "$1" >/dev/null 2>&1; }

sudo_run() {
	if [ "$(id -u)" -eq 0 ]; then "$@"; else sudo "$@"; fi
}

# --- where things live -----------------------------------------------------------

config_home="${XDG_CONFIG_HOME:-$HOME/.config}"
state_home="${XDG_STATE_HOME:-$HOME/.local/state}"
cache_home="${XDG_CACHE_HOME:-$HOME/.cache}"
unit_dir="$config_home/systemd/user"
rule_path="/etc/udev/rules.d/$RULE"

# A file from the repo: the local checkout when there is one, else the chosen ref.
repo_file() {
	if [ -n "$source_dir" ] && [ -f "$source_dir/$1" ]; then
		cat "$source_dir/$1"
	elif [ -f "$(dirname "$0")/$1" ] && [ -f "$(dirname "$0")/pyproject.toml" ]; then
		cat "$(dirname "$0")/$1"
	else
		curl -fsSL "https://raw.githubusercontent.com/$REPO/$ref/$1"
	fi
}

# --- uninstalling ----------------------------------------------------------------

if [ "$uninstall" -eq 1 ]; then
	bold "Uninstalling Pushtoo"
	if [ -f "$unit_dir/$SERVICE" ] && ask "Stop and remove the background service?" y; then
		systemctl --user disable --now "$SERVICE" 2>/dev/null || true
		rm -f "$unit_dir/$SERVICE"
		systemctl --user daemon-reload 2>/dev/null || true
		say "Service removed."
	fi
	if have uv && uv tool list --color never 2>/dev/null | grep -q '^pushtoo ' && ask "Remove the pushtoo command?" y; then
		uv tool uninstall pushtoo
	fi
	if [ -f "$rule_path" ] && ask "Remove the udev rule ($rule_path, needs sudo)?" y; then
		sudo_run rm -f "$rule_path"
		sudo_run udevadm control --reload || true
	fi
	if [ "$purge" -eq 1 ]; then
		say "Your profiles, themes and saved state:"
		say "  $config_home/pushtoo  $state_home/pushtoo  $cache_home/pushtoo"
		if ask "Delete them? This can't be undone." n; then
			rm -rf "$config_home/pushtoo" "$state_home/pushtoo" "$cache_home/pushtoo"
			say "Deleted."
		fi
	else
		say "Kept your profiles and themes in $config_home/pushtoo (--purge removes them)."
	fi
	say "The audio group and system packages were left as they are."
	exit 0
fi

# --- what this system needs ------------------------------------------------------

distro_id=""
distro_like=""
if [ -r /etc/os-release ]; then
	# shellcheck disable=SC1091
	. /etc/os-release
	distro_id="${ID:-}"
	distro_like="${ID_LIKE:-}"
fi

packages=""
install_cmd=""
case " $distro_id $distro_like " in
*" arch "*)
	packages="cairo pkgconf base-devel alsa-lib libusb"
	install_cmd="pacman -S --needed --noconfirm $packages" ;;
*" debian "* | *" ubuntu "* | *" raspbian "*)
	packages="libcairo2-dev pkg-config build-essential libasound2 libusb-1.0-0"
	install_cmd="apt-get install -y $packages" ;;
*" fedora "* | *" rhel "*)
	packages="cairo-devel pkgconf-pkg-config gcc alsa-lib libusb1"
	install_cmd="dnf install -y $packages" ;;
esac

in_audio_group=0
if id -nG "$(id -un)" | tr ' ' '\n' | grep -qx audio; then in_audio_group=1; fi
have_systemd_user=0
if have systemctl && systemctl --user show-environment >/dev/null 2>&1; then have_systemd_user=1; fi

# --- the questions -----------------------------------------------------------------

bold "Pushtoo installer"
say "Pushtoo turns an Ableton Push 2 into an instrument for any synth or DAW."
say "Nothing changes until you've answered every question and confirmed."

do_packages=0
do_uv=0
do_pushtoo=0
do_udev=0
do_group=0
do_service=0
do_start=0

step "1. System packages"
if [ "$skip_packages" -eq 1 ]; then
	say "Skipped (--no-packages)."
elif [ -z "$install_cmd" ]; then
	say "This system ($distro_id) isn't one I know packages for. Pushtoo needs, by"
	say "whatever names your system uses: the cairo library and its headers, pkg-config,"
	say "a C compiler, the ALSA library and libusb 1.0. Install those yourself if needed."
else
	say "Pushtoo builds two of its parts from source, which needs:"
	say "  sudo $install_cmd"
	if ask "Install these system packages?" y; then do_packages=1; fi
fi

step "2. uv"
if have uv; then
	say "Already installed ($(uv --version))."
else
	say "uv installs Pushtoo in its own environment, with its own Python, so it can't"
	say "clash with anything else on your system. Its official installer puts it in"
	say "$HOME/.local/bin."
	if ask "Install uv?" y; then do_uv=1; fi
fi

step "3. Pushtoo"
if [ -n "$source_dir" ]; then what="from $source_dir"; else what="version $ref from GitHub"; fi
if have pushtoo; then say "Pushtoo is installed; this will upgrade it ($what)."; fi
if ask "Install Pushtoo ($what) as the pushtoo command?" y; then do_pushtoo=1; fi

step "4. Using the Push display and Undo keys without root"
if [ "$skip_udev" -eq 1 ]; then
	say "Skipped (--no-udev)."
else
	say "A udev rule lets your user (and the audio group) open the Push's display and"
	say "type Undo shortcuts. Desktop logins often have this already; the rule makes"
	say "sure, and covers headless use (a Raspberry Pi, SSH, the background service)."
	say "It's installed as $rule_path (sudo)."
	if ask "Install the udev rule?" y; then do_udev=1; fi
	if [ "$in_audio_group" -eq 1 ]; then
		say "You're already in the audio group."
	else
		say "The rule grants access to the audio group, which you're not in."
		if ask "Add $(id -un) to the audio group (sudo; takes effect at your next login)?" y; then
			do_group=1
		fi
	fi
fi

step "5. Starting at login"
if [ "$skip_service" -eq 1 ]; then
	say "Skipped (--no-service)."
elif [ "$have_systemd_user" -eq 0 ]; then
	say "No systemd user session here, so no background service. Run pushtoo yourself."
else
	say "Pushtoo can run in the background from login and wait for the Push, so plugging"
	say "it in is all it takes. It uses almost no CPU while waiting, sends all notes off"
	say "when stopped, and you can stop or remove it any time (see the README)."
	if ask "Start Pushtoo automatically when you log in?" y; then
		do_service=1
		if [ "$skip_start" -eq 1 ]; then
			say "Not starting it now (--no-start)."
		elif ask "Start it now as well?" y; then
			do_start=1
		fi
	fi
fi

# --- recap -------------------------------------------------------------------------

step "Your choices"
yesno() { if [ "$1" -eq 1 ]; then printf 'yes'; else printf 'no'; fi; }
say "  System packages:          $(yesno "$do_packages")"
say "  Install uv:               $(yesno "$do_uv")"
say "  Install Pushtoo:          $(yesno "$do_pushtoo")"
say "  udev rule:                $(yesno "$do_udev")"
say "  Join the audio group:     $(yesno "$do_group")"
say "  Start at login:           $(yesno "$do_service")"
say "  Start now:                $(yesno "$do_start")"
if ! ask "Go ahead?" y; then
	say "Nothing was changed."
	exit 0
fi

# --- doing it ------------------------------------------------------------------------

if [ "$do_packages" -eq 1 ]; then
	step "Installing system packages"
	case "$install_cmd" in apt-get*) sudo_run apt-get update ;; esac
	# shellcheck disable=SC2086 # the package list splits into words on purpose
	sudo_run $install_cmd
fi

if [ "$do_uv" -eq 1 ]; then
	step "Installing uv"
	curl -LsSf https://astral.sh/uv/install.sh | sh
	PATH="$HOME/.local/bin:$PATH"
	export PATH
fi

if [ "$do_pushtoo" -eq 1 ]; then
	step "Installing Pushtoo"
	if ! have uv; then
		say "uv isn't installed, so Pushtoo can't be. Re-run and let it install uv." >&2
		exit 1
	fi
	if [ -n "$source_dir" ]; then
		target="$source_dir"
	else
		target="git+https://github.com/$REPO@$ref"
	fi
	uv tool install --force --python 3.12 "$target"
fi

bin_dir="$(uv tool dir --bin --color never 2>/dev/null || printf '%s' "$HOME/.local/bin")"
pushtoo_bin="$bin_dir/pushtoo"

if [ "$do_udev" -eq 1 ]; then
	step "Installing the udev rule"
	repo_file "packaging/udev/$RULE" | sudo_run tee "$rule_path" >/dev/null
	sudo_run udevadm control --reload
	sudo_run udevadm trigger
fi

if [ "$do_group" -eq 1 ]; then
	step "Adding you to the audio group"
	sudo_run usermod -aG audio "$(id -un)"
	say "Done; it takes effect the next time you log in."
fi

if [ "$do_service" -eq 1 ]; then
	step "Setting up the background service"
	mkdir -p "$unit_dir"
	repo_file "packaging/systemd/$SERVICE" |
		sed "s|^ExecStart=.*|ExecStart=$pushtoo_bin|" >"$unit_dir/$SERVICE"
	systemctl --user daemon-reload
	systemctl --user enable "$SERVICE"
	if [ "$do_start" -eq 1 ]; then
		systemctl --user restart "$SERVICE"
		say "Running. Its log: journalctl --user -u pushtoo -f"
	fi
fi

step "Checking"
if [ -x "$pushtoo_bin" ]; then
	"$pushtoo_bin" doctor || true
else
	say "pushtoo isn't installed yet, so there's nothing to check."
fi

step "Next"
say "1. Plug in your Push 2."
if [ "$do_service" -eq 0 ]; then say "   Then run: pushtoo"; fi
say "2. In your DAW or synth, choose the MIDI input \"Pushtoo Out\"."
say "3. Play. If something's not right: pushtoo doctor"
case ":$PATH:" in
*":$bin_dir:"*) ;;
*) say "Note: $bin_dir isn't on your PATH; add it to run pushtoo by name." ;;
esac
