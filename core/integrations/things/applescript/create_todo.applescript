-- Create a new to-do in Things 3
-- Usage: osascript create_todo.applescript "Task name" "Notes" "2025-01-20" "Project Name" "list"
-- Args: name, notes, when_date (YYYY-MM-DD or empty), project (or empty), list (today/inbox/anytime/someday)
-- Returns: the Things ID of the created to-do

on run argv
    set taskName to item 1 of argv
    set taskNotes to item 2 of argv
    set whenDateStr to item 3 of argv
    set projectName to item 4 of argv
    set listName to item 5 of argv

    tell application "Things3"
        -- Build properties
        set taskProps to {name:taskName}

        -- Add notes if provided
        if taskNotes is not "" then
            set taskProps to taskProps & {notes:taskNotes}
        end if

        -- Parse when date if provided (will schedule after creation)
        set scheduleDate to missing value
        if whenDateStr is not "" then
            -- Parse YYYY-MM-DD format using current date as base
            set y to (text 1 thru 4 of whenDateStr) as integer
            set m to (text 6 thru 7 of whenDateStr) as integer
            set d to (text 9 thru 10 of whenDateStr) as integer

            -- Create date by modifying current date
            set scheduleDate to current date
            set year of scheduleDate to y
            set month of scheduleDate to m
            set day of scheduleDate to d
            set hours of scheduleDate to 0
            set minutes of scheduleDate to 0
            set seconds of scheduleDate to 0
        end if

        -- Create the to-do
        if projectName is not "" then
            -- Create in a specific project
            try
                set targetProject to project named projectName
                set newToDo to make new to do with properties taskProps at beginning of targetProject
            on error
                -- Project not found, create in inbox
                set newToDo to make new to do with properties taskProps
            end try
        else
            -- Create in specified list
            set newToDo to make new to do with properties taskProps

            -- Move to appropriate list (only if no schedule date)
            if scheduleDate is missing value then
                if listName is "today" then
                    move newToDo to list "Today"
                else if listName is "anytime" then
                    move newToDo to list "Anytime"
                else if listName is "someday" then
                    move newToDo to list "Someday"
                end if
            end if
            -- inbox is the default, no move needed
        end if

        -- Schedule the task for the when date (this sets the "When" field, not deadline)
        if scheduleDate is not missing value then
            schedule newToDo for scheduleDate
        end if

        -- Return the ID
        return id of newToDo
    end tell
end run
