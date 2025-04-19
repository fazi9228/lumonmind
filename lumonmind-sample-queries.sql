-- 1. Find all upcoming appointments for a specific user with specialist details
SELECT 
    a.AppointmentID, 
    a.AppointmentDateTime, 
    a.Type,
    a.Status,
    s.Name AS SpecialistName,
    s.Credentials,
    s.HourlyRate
FROM 
    Appointments a
JOIN 
    Specialists s ON a.SpecialistID = s.SpecialistID
WHERE 
    a.UserID = 123
    AND a.AppointmentDateTime > CURRENT_TIMESTAMP
    AND a.Status = 'scheduled'
ORDER BY 
    a.AppointmentDateTime;

-- 2. Get all specialists with their specializations
SELECT 
    s.SpecialistID,
    s.Name,
    s.Credentials,
    s.IsActive,
    string_agg(sp.Name, ', ') AS Specializations
FROM 
    Specialists s
LEFT JOIN 
    SpecialistSpecializations ss ON s.SpecialistID = ss.SpecialistID
LEFT JOIN 
    Specializations sp ON ss.SpecializationID = sp.SpecializationID
GROUP BY 
    s.SpecialistID, s.Name, s.Credentials, s.IsActive
ORDER BY 
    s.Name;

-- 3. Find available time slots for a specific specialist on a given day
SELECT 
    sa.StartTime, 
    sa.EndTime
FROM 
    SpecialistAvailability sa
LEFT JOIN 
    (SELECT 
        AppointmentDateTime, 
        EndDateTime
     FROM 
        Appointments
     WHERE 
        SpecialistID = 5
        AND Status = 'scheduled'
        AND DATE(AppointmentDateTime) = '2025-04-25') a
    ON (sa.StartTime, sa.EndTime) OVERLAPS (a.AppointmentDateTime::time, a.EndDateTime::time)
WHERE 
    sa.SpecialistID = 5
    AND sa.DayOfWeek = 'Friday'
    AND sa.IsRecurring = TRUE
    AND '2025-04-25' BETWEEN sa.EffectiveDate AND COALESCE(sa.ExpiryDate, '2099-12-31')
    AND a.AppointmentDateTime IS NULL
ORDER BY 
    sa.StartTime;

-- 4. Get user conversation history with detected topics (if session storage is implemented)
SELECT 
    s.SessionID,
    s.StartTime,
    s.EndTime,
    COUNT(m.MessageID) AS MessageCount,
    jsonb_array_elements_text(m.DetectedTopics) AS TopicName
FROM 
    Sessions s
JOIN 
    Messages m ON s.SessionID = m.SessionID
WHERE 
    s.UserID = 456
    AND s.SessionStatus = 'completed'
GROUP BY 
    s.SessionID, s.StartTime, s.EndTime, jsonb_array_elements_text(m.DetectedTopics)
ORDER BY 
    s.StartTime DESC;

-- 5. Get feedback statistics for specialists
SELECT 
    s.SpecialistID,
    s.Name,
    COUNT(f.FeedbackID) AS FeedbackCount,
    ROUND(AVG(f.Rating), 1) AS AverageRating,
    COUNT(CASE WHEN f.Rating >= 4 THEN 1 ELSE NULL END) AS PositiveFeedbacks,
    COUNT(CASE WHEN f.Rating <= 2 THEN 1 ELSE NULL END) AS NegativeFeedbacks
FROM 
    Specialists s
LEFT JOIN 
    Feedback f ON f.RelatedID = s.SpecialistID AND f.Category = 'specialist-session'
GROUP BY 
    s.SpecialistID, s.Name
ORDER BY 
    AverageRating DESC;

-- 6. Find most popular mental health topics based on user interests
SELECT 
    t.TopicName,
    COUNT(ut.UserID) AS InterestedUsersCount
FROM 
    Topics t
JOIN 
    UserTopics ut ON t.TopicID = ut.TopicID
GROUP BY 
    t.TopicID, t.TopicName
ORDER BY 
    InterestedUsersCount DESC;

-- 7. Find specialists available for appointment for a specific topic/specialization
SELECT 
    s.SpecialistID,
    s.Name,
    s.HourlyRate,
    string_agg(DISTINCT sp.Name, ', ') AS Specializations,
    string_agg(DISTINCT FORMAT('%s %s-%s', sa.DayOfWeek, sa.StartTime::text, sa.EndTime::text), ', ') AS AvailableTimes
FROM 
    Specialists s
JOIN 
    SpecialistSpecializations ss ON s.SpecialistID = ss.SpecialistID
JOIN 
    Specializations sp ON ss.SpecializationID = sp.SpecializationID
JOIN 
    SpecialistAvailability sa ON s.SpecialistID = sa.SpecialistID
WHERE 
    s.IsActive = TRUE
    AND sp.Name = 'Anxiety'
    AND sa.IsRecurring = TRUE
    AND CURRENT_DATE BETWEEN sa.EffectiveDate AND COALESCE(sa.ExpiryDate, '2099-12-31')
GROUP BY 
    s.SpecialistID, s.Name, s.HourlyRate
ORDER BY 
    s.HourlyRate;

-- 8. Comprehensive user activity report with session and appointment info
SELECT 
    u.UserID,
    u.Name,
    u.Email,
    u.UserType,
    u.JoinDate,
    COUNT(DISTINCT s.SessionID) AS TotalSessions,
    MAX(s.EndTime) AS LastSessionDate,
    COUNT(DISTINCT a.AppointmentID) AS TotalAppointments,
    COUNT(DISTINCT CASE WHEN a.Status = 'completed' THEN a.AppointmentID ELSE NULL END) AS CompletedAppointments,
    COUNT(DISTINCT CASE WHEN a.Status = 'scheduled' AND a.AppointmentDateTime > CURRENT_TIMESTAMP THEN a.AppointmentID ELSE NULL END) AS UpcomingAppointments,
    ROUND(AVG(CASE WHEN f.Category = 'ai-interaction' THEN f.Rating ELSE NULL END), 1) AS AvgAIRating,
    ROUND(AVG(CASE WHEN f.Category = 'specialist-session' THEN f.Rating ELSE NULL END), 1) AS AvgSpecialistRating
FROM 
    Users u
LEFT JOIN 
    Sessions s ON u.UserID = s.UserID
LEFT JOIN 
    Appointments a ON u.UserID = a.UserID
LEFT JOIN 
    Feedback f ON u.UserID = f.UserID
GROUP BY 
    u.UserID, u.Name, u.Email, u.UserType, u.JoinDate
ORDER BY 
    u.JoinDate DESC;

-- MASTER QUERY for consolidated dashboard/reporting
-- This query joins all main tables to provide a comprehensive view of the system
SELECT 
    -- User Information
    u.UserID,
    u.Name AS UserName,
    u.UserType,
    u.JoinDate,
    u.LastLoginDate,
    u.PreferredLanguage,
    
    -- User Topics of Interest
    (SELECT string_agg(t.TopicName, ', ') 
     FROM UserTopics ut 
     JOIN Topics t ON ut.TopicID = t.TopicID 
     WHERE ut.UserID = u.UserID) AS UserInterests,
    
    -- Session Information (if implemented)
    COUNT(DISTINCT s.SessionID) AS TotalSessions,
    MAX(s.StartTime) AS LastSessionStart,
    SUM(EXTRACT(EPOCH FROM (s.EndTime - s.StartTime))/60)::INTEGER AS TotalSessionMinutes,
    
    -- Topics from Sessions (if implemented)
    (SELECT string_agg(DISTINCT jsonb_array_elements_text(m.DetectedTopics)::text, ', ') 
     FROM Sessions s2 
     JOIN Messages m ON s2.SessionID = m.SessionID 
     WHERE s2.UserID = u.UserID) AS DetectedTopics,
    
    -- Appointment Information
    COUNT(DISTINCT a.AppointmentID) AS TotalAppointments,
    COUNT(DISTINCT CASE WHEN a.Status = 'completed' THEN a.AppointmentID END) AS CompletedAppointments,
    COUNT(DISTINCT CASE WHEN a.Status = 'canceled' THEN a.AppointmentID END) AS CanceledAppointments,
    COUNT(DISTINCT CASE WHEN a.Status = 'no-show' THEN a.AppointmentID END) AS NoShowAppointments,
    COUNT(DISTINCT CASE WHEN a.Status = 'scheduled' AND a.AppointmentDateTime > CURRENT_TIMESTAMP THEN a.AppointmentID END) AS UpcomingAppointments,
    MAX(a.AppointmentDateTime) AS LastAppointmentDate,
    
    -- Specialist Engagement
    COUNT(DISTINCT a.SpecialistID) AS UniqueSpecialistsConsulted,
    (SELECT string_agg(DISTINCT sp.Name, ', ') 
     FROM Appointments a2 
     JOIN Specialists s ON a2.SpecialistID = s.SpecialistID 
     JOIN SpecialistSpecializations ss ON s.SpecialistID = ss.SpecialistID 
     JOIN Specializations sp ON ss.SpecializationID = sp.SpecializationID 
     WHERE a2.UserID = u.UserID) AS SpecializationsAccessed,
    
    -- Feedback Information
    ROUND(AVG(CASE WHEN f.Category = 'ai-interaction' THEN f.Rating END), 1) AS AvgAIFeedback,
    COUNT(CASE WHEN f.Category = 'ai-interaction' THEN f.FeedbackID END) AS AIFeedbackCount,
    ROUND(AVG(CASE WHEN f.Category = 'specialist-session' THEN f.Rating END), 1) AS AvgSpecialistFeedback,
    COUNT(CASE WHEN f.Category = 'specialist-session' THEN f.FeedbackID END) AS SpecialistFeedbackCount,
    
    -- System Usage Metrics
    (SELECT COUNT(*) FROM AuditLogs al WHERE al.UserID = u.UserID) AS TotalAuditEvents,
    (SELECT MAX(al.Timestamp) FROM AuditLogs al WHERE al.UserID = u.UserID) AS LastActivity
    
FROM 
    Users u
LEFT JOIN 
    Sessions s ON u.UserID = s.UserID
LEFT JOIN 
    Appointments a ON u.UserID = a.UserID
LEFT JOIN 
    Feedback f ON u.UserID = f.UserID
GROUP BY 
    u.UserID, u.Name, u.UserType, u.JoinDate, u.LastLoginDate, u.PreferredLanguage
ORDER BY 
    u.JoinDate DESC;
