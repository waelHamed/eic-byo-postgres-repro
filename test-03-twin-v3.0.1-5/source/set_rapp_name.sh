#!/bin/bash

set -e

# Defining ANSI color codes for terminal output
RED='\e[0;31m'
LIGHT_RED='\e[0;91m'
ORANGE='\e[38;5;208m'
YELLOW='\e[0;33m'
GREEN='\e[38;5;10m'
BLUE='\e[38;5;81m'
DEFAULT='\e[0m'

# More reliable than `sed -i` if we're on WSL and handling Windows paths
wsl_safe_sed_replace() {
  local pattern=$1
  local file=$2
  local tmpfile
  tmpfile=$(mktemp "${file}.XXXXXX") || exit 1
  chmod "$(stat --format=%a $file)" "$tmpfile"
  sed "$pattern" "$file" > "$tmpfile" && mv -f "$tmpfile" "$file"
}

echo -e "\n${ORANGE}=================Executing renaming script=================${DEFAULT}"

if [[ -z "$RAPP_NAME" ]]; then
  echo -e "${RED}\n===========================================================${DEFAULT}"
  echo -e "${RED}Error${DEFAULT}: ${BLUE}RAPP_NAME${DEFAULT} environment variable must be set. Exiting..."
  echo -e "${RED}===========================================================\n${DEFAULT}"
  exit 1
fi

if [[ "$RAPP_NAME" != "RAPP_NAME" ]]; then
  if ! [[ "$RAPP_NAME" =~ ^[a-z0-9]([-a-z0-9]*[a-z0-9])?$ ]]; then
    echo -e "${RED}\n===========================================================${DEFAULT}"
    echo -e "${RED}Error${DEFAULT}: New rApp name '$RAPP_NAME' is not a valid Helm chart name."
    echo -e "It must:"
    echo -e "  - Use only lowercase letters, numbers, and dashes (-)"
    echo -e "  - Start and end with an alphanumeric character"
    echo -e "Exiting..."
    echo -e "${RED}===========================================================\n${DEFAULT}"
    exit 1
  fi
else
  echo -e "\n${LIGHT_RED}WARNING${DEFAULT}: RAPP_NAME can be set only as a placeholder. RAPP_NAME is not a valid name for development purposes"
fi

if [[ ${#RAPP_NAME} -gt 53 ]]; then
  echo -e "${RED}\n===========================================================${DEFAULT}"
  echo -e "The ${BLUE}RAPP_NAME${DEFAULT} exceeds 53 characters. Helm chart name must be at most 53 characters. ${RED}Exiting...${DEFAULT}"
  echo -e "${RED}===========================================================\n${DEFAULT}"
  exit 1
fi

# Setting target directory
if [[ -z "$1"  ]]; then
  TARGET_DIR="${TARGET_DIR:-$(pwd)}"
else
  TARGET_DIR=$1
fi

echo -e "\nUsing ${BLUE}TARGET_DIR${DEFAULT} as: $TARGET_DIR"

# List of target paths that need to be renamed
INPUT_PATHS=("charts/" "csar/" "network_data_template_app/" "tests/")

# Print directories
if [[ ${#INPUT_PATHS[@]} -gt 0 ]]; then
  echo -e "\nExecuting the script in the following directories:"
  for path in "${INPUT_PATHS[@]}"; do
    if [[ ! -e "${TARGET_DIR}/${path}" ]]; then
      echo -e "${RED}\n===========================================================${DEFAULT}"
      echo -e "${RED}Error${DEFAULT}: directory '$path' does not exist. Exiting..."
      echo -e "${RED}===========================================================\n${DEFAULT}"
      exit 1
    fi
    echo " - $path"
  done

  count=0
  for path in "${INPUT_PATHS[@]}"; do
    INPUT_PATHS[$count]="${TARGET_DIR}/${path}"
    count=$((count + 1))
  done
else
  INPUT_PATHS=("$TARGET_DIR")
fi

chart_dirs=()

# Collect the rApp's chart(s)
for path in "${INPUT_PATHS[@]}"; do
  if [[ -d "$path" && -d "$path/charts" ]]; then
    chart_dirs+=("$path/charts"/*)
  fi
  if [[ "$(basename "$path")" == "charts" && -d "$path" ]]; then
    chart_dirs+=("${path%/}"/*)
  fi
done

# Expect only one chart present and assume we can use its name as our RAPP_NAME
if [[ ! -d "${chart_dirs[0]}" || ${#chart_dirs[@]} -ne 1 ]]; then
  echo -e "${RED}\n===========================================================${DEFAULT}"
  echo -e "${RED}Error${DEFAULT}: No valid subdirectories found in provided paths' charts/ directories."
  echo -e "${RED}===========================================================\n${DEFAULT}"
  exit 1
fi

CURRENT_RAPP_NAME=$(basename "${chart_dirs[0]}")
echo -e "\nDetected ${BLUE}CURRENT_RAPP_NAME${DEFAULT} as '$CURRENT_RAPP_NAME'"

if [[ "$CURRENT_RAPP_NAME" == "$RAPP_NAME" ]]; then
  echo -e "\n${RED}Provided ${BLUE}RAPP_NAME${RED} is the same as ${BLUE}CURRENT_RAPP_NAME${RED}. Exiting...${DEFAULT}"
  exit 1
fi

script_file=$(basename "$0")

echo -e "\nReplacing '$CURRENT_RAPP_NAME' with '$RAPP_NAME'...\n"

echo -e "${YELLOW}Updating file contents...${DEFAULT}"
for path in "${INPUT_PATHS[@]}"; do
  grep -rl "$CURRENT_RAPP_NAME" "$path" | while read -r file; do
    if [[ $(basename "$file") != "$script_file" && $(basename "$file") != docker.tar* ]]; then
      wsl_safe_sed_replace "s/$CURRENT_RAPP_NAME/$RAPP_NAME/g" "$file"
    fi
  done
done

echo -e "${YELLOW}Renaming files...${DEFAULT}"
for path in "${INPUT_PATHS[@]}"; do
  find "$path" -depth -type f -name "*$CURRENT_RAPP_NAME*" | while read -r file; do
    if [[ $(basename "$file") != "$script_file" ]]; then
      newfile="$(dirname "$file")/$(basename "$file" | sed "s/$CURRENT_RAPP_NAME/$RAPP_NAME/g")"
      mv -f "$file" "$newfile"
    fi
  done
done

echo -e "${YELLOW}Renaming directories...${DEFAULT}"
for path in "${INPUT_PATHS[@]}"; do
  find "$path" -depth -type d -name "*$CURRENT_RAPP_NAME*" | while read -r dir; do
    # Skip renaming the outermost directory itself
    if [[ "$(realpath "$dir")" == "$(realpath "$path")" ]]; then
      continue
    fi

    newdir="$(dirname "$dir")/$(basename "$dir" | sed "s/$CURRENT_RAPP_NAME/$RAPP_NAME/g")"
    mv -f "$dir" "$newdir"
  done
done

echo -e "${GREEN}\n===========================================================${DEFAULT}"
echo -e "${GREEN}Finished renaming.${DEFAULT}"
echo -e "${GREEN}===========================================================\n${DEFAULT}"