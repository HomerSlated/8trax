#!/usr/bin/env fish

set -g manifest (dirname (status filename))/backup.manifest
set -g dry_run 0
set -g force 0

# -------------------------
# Parse command + global flags
# -------------------------

if test (count $argv) -eq 0
    echo "Error: no command given"
    echo "Usage:"
    echo "  "(basename (status filename))" backup  [--dry-run]"
    echo "  "(basename (status filename))" restore [--dry-run] [--force]"
    echo "  "(basename (status filename))" clean   [--dry-run]"
    exit 1
end

set -g cmd $argv[1]

for arg in $argv[2..-1]
    switch $arg
        case --dry-run
            set -g dry_run 1
        case --force
            set -g force 1
    end
end

# -------------------------
# Validate manifest
# -------------------------

if not test -f $manifest
    echo "Error: $manifest not found"
    exit 1
end

# -------------------------
# Load file list (skip blank lines and comments)
# -------------------------

set -g files
for line in (cat $manifest)
    set line (string trim $line)
    if test -z "$line"
        continue
    end
    if string match -q '#*' $line
        continue
    end
    set -g files $files $line
end

# -------------------------
# Helpers
# -------------------------

function latest_backup
    set file $argv[1]
    set dir (dirname $file)
    set name (basename $file)
    # Closing the quote after $name forces Fish to stop reading the variable
    # name there, preventing $name_ from being parsed as variable "name_"
    set backups (path filter -f "$dir/$name"_*.bak 2>/dev/null | sort -V)
    if test (count $backups) -eq 0
        echo ""
        return
    end
    echo $backups[-1]
end

# -------------------------
# BACKUP
# -------------------------

function do_backup
    set uin (date +%Y%m%d%H%M%S)
    for file in $files
        if not test -f $file
            echo "Skipping missing file: $file"
            continue
        end
        set dir (dirname $file)
        set name (basename $file)
        set bak "$dir/$name"_"$uin.bak"
        if test $dry_run -eq 1
            echo "[DRY] cp $file → $bak"
        else
            echo "Backing up $file → $bak"
            cp "$file" "$bak"
        end
    end
end

# -------------------------
# RESTORE
# -------------------------

function do_restore
    for file in $files
        set latest (latest_backup $file)
        if test -z "$latest"
            echo "No backup found for $file"
            continue
        end
        if test -f $file
            if diff -q "$file" "$latest" >/dev/null
                echo "Skipping $file — identical to latest backup"
                continue
            end
        end
        if test $dry_run -eq 1
            echo "[DRY] restore $latest → $file"
            continue
        end
        echo "Restoring $file from $latest"
        if test $force -eq 1
            cp "$latest" "$file"
        else
            cp -i "$latest" "$file"
        end
    end
end

# -------------------------
# CLEAN (keep latest backup only)
# -------------------------

function do_clean
    for file in $files
        set dir (dirname $file)
        set name (basename $file)
        # Closing the quote after $name prevents Fish reading $name_ as variable "name_"
        set backups (path filter -f "$dir/$name"_*.bak 2>/dev/null | sort -V)
        if test (count $backups) -le 1
            continue
        end
        set newest $backups[-1]
        for b in $backups
            if test "$b" != "$newest"
                if test $dry_run -eq 1
                    echo "[DRY] rm $b"
                else
                    echo "Deleting $b"
                    rm -f "$b"
                end
            end
        end
    end
end

# -------------------------
# Dispatch
# -------------------------

switch $cmd
    case backup
        do_backup
    case restore
        do_restore
    case clean
        do_clean
    case '*'
        echo "Unknown command: $cmd"
        echo "Usage:"
        echo "  "(basename (status filename))" backup  [--dry-run]"
        echo "  "(basename (status filename))" restore [--dry-run] [--force]"
        echo "  "(basename (status filename))" clean   [--dry-run]"
        exit 1
end
