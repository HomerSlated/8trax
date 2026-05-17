#!/usr/bin/env fish

set log_file /tmp/sync.log
set script_dir (dirname (status filename))

# -------------------------
# Parse flags
# -------------------------

set commit_message ""

for arg in $argv
    switch $arg
        case -m --message
            set next_is_message 1
        case '*'
            if set -q next_is_message
                set commit_message $arg
                set -e next_is_message
            end
    end
end

if test -z "$commit_message"
    echo "Error: commit message required (-m|--message)"
    exit 1
end

# -------------------------
# Truncate log
# -------------------------

: > $log_file

# -------------------------
# Capture changes before begin block
# -------------------------

set changes (git status --porcelain)

begin
    git status
    if test -n "$changes"
        echo "🔄 Changes detected. Syncing..."
        git add -v .
        git commit -m "$commit_message"
        git push -u origin main
        fish "$script_dir/backup.fish" backup
        echo "✅ Sync complete."
    else
        echo "✅ No changes to sync."
    end
end 2>&1 | tee -a $log_file
