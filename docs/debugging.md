# Debugging Guide

## Temporary Logging Setup

This guide explains how to capture terminal output to log files for debugging purposes.

### Files Created
- `log.txt` - Temporary log file for capturing terminal output
- `.gitignore` - Updated to ignore log files (`log.txt`, `debug.log`, `*.log`)

### Usage Methods

#### Method 1: Redirect All Output (Recommended)
```bash
python main.py 2>&1 | tee log.txt
```
- Captures both stdout and stderr
- Shows output in terminal AND saves to file
- Overwrites log file on each run

#### Method 2: Just Error Output
```bash
python main.py 2> log.txt
```
- Captures only stderr (error messages)
- Saves to file, doesn't show in terminal
- Overwrites log file on each run

#### Method 3: Append to Log (Keep Previous Runs)
```bash
python main.py 2>> log.txt
```
- Captures stderr and appends to existing log
- Preserves previous run logs
- Good for tracking issues over multiple sessions

#### Method 4: Both stdout and stderr (Terminal Only)
```bash
python main.py > log.txt 2>&1
```
- Captures both stdout and stderr
- Saves to file, doesn't show in terminal
- Overwrites log file on each run

### Quick Commands

#### Run with Logging
```bash
# Capture all output and see in terminal
python main.py 2>&1 | tee log.txt
```

#### View the Log
```bash
# View entire log
cat log.txt

# View last 50 lines
tail -50 log.txt

# Follow log in real-time
tail -f log.txt
```

#### Search Logs
```bash
# Search for specific messages
grep "CACHE REFRESH" log.txt

# Search with context (lines before/after)
grep -C 3 "CACHE REFRESH" log.txt

# Search for multiple patterns
grep -E "(CACHE|DEBUG|ERROR)" log.txt
```

### Common Debugging Scenarios

#### Cache Widget Positioning Issues
```bash
# Run and capture cache-related logs
python main.py 2>&1 | tee log.txt

# Search for cache refresh messages
grep -A 5 -B 5 "CACHE REFRESH" log.txt

# Search for widget positioning
grep -A 3 -B 3 "Inserted cache widget" log.txt
```

#### Progress Window Issues
```bash
# Search for progress window messages
grep -i "progress" log.txt

# Look for threading issues
grep -i "thread" log.txt
```

#### Error Investigation
```bash
# Find all error messages
grep -i "error" log.txt

# Find exceptions with stack traces
grep -A 10 "Exception\|Error" log.txt
```

### Log File Management

#### Clean Up
```bash
# Remove log file
rm log.txt

# Clear log file (keep file but empty contents)
> log.txt

# Archive old logs
mv log.txt log_$(date +%Y%m%d_%H%M%S).txt
```

#### Git Integration
The log files are automatically ignored by git, so they won't be committed:
```bash
# Check what's ignored
git status --ignored

# Ensure log files are ignored
git check-ignore log.txt
```

### Tips for Effective Debugging

1. **Use Method 1 (`tee`) for interactive debugging** - See output live and save to file
2. **Search with context (`-C` flag)** - Get surrounding lines for better understanding
3. **Use timestamps** - Add date/time to log filenames for multiple sessions
4. **Focus on relevant patterns** - Search for specific issues rather than reading entire logs
5. **Clean up regularly** - Remove old log files to avoid clutter

### Example Debugging Workflow

```bash
# 1. Start fresh logging session
> log.txt

# 2. Run application with logging
python main.py 2>&1 | tee log.txt

# 3. Reproduce the issue
# (interact with the application)

# 4. Search for relevant messages
grep -A 5 -B 5 "cache widget" log.txt

# 5. Analyze the findings
# (review the grep output)

# 6. Clean up if needed
rm log.txt
```

This setup provides a comprehensive logging solution for debugging application issues without cluttering the git repository.
