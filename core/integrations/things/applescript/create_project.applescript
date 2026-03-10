-- Create a new project in Things 3 if it doesn't exist
-- Usage: osascript create_project.applescript "Project Name"
-- Returns: the Things ID of the project (existing or new)

on run argv
    set projectName to item 1 of argv

    tell application "Things3"
        -- Check if project already exists
        try
            set existingProject to project named projectName
            return "exists:" & (id of existingProject)
        on error
            -- Project doesn't exist, create it
            set newProject to make new project with properties {name:projectName}
            return "created:" & (id of newProject)
        end try
    end tell
end run
