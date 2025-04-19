-- Users table
CREATE TABLE Users (
    UserID SERIAL PRIMARY KEY,
    Name VARCHAR(100) NOT NULL,
    Email VARCHAR(100) UNIQUE,
    Phone VARCHAR(20),
    Password VARCHAR(100),
    UserType VARCHAR(20) NOT NULL DEFAULT 'guest',
    JoinDate DATE NOT NULL DEFAULT CURRENT_DATE,
    LastLoginDate TIMESTAMP,
    PreferredLanguage VARCHAR(20) DEFAULT 'English',
    CONSTRAINT chk_user_type CHECK (UserType IN ('guest', 'registered'))
);

-- Topics table
CREATE TABLE Topics (
    TopicID SERIAL PRIMARY KEY,
    TopicName VARCHAR(50) NOT NULL UNIQUE,
    Description TEXT,
    KeywordsList JSONB
);

-- Specialists table
CREATE TABLE Specialists (
    SpecialistID SERIAL PRIMARY KEY,
    Name VARCHAR(100) NOT NULL,
    Credentials VARCHAR(200) NOT NULL,
    ContactInfo JSONB NOT NULL,
    Biography TEXT,
    ProfilePicture VARCHAR(255),
    IsActive BOOLEAN DEFAULT TRUE,
    HourlyRate DECIMAL(10, 2)
);

-- Specializations table
CREATE TABLE Specializations (
    SpecializationID SERIAL PRIMARY KEY,
    Name VARCHAR(100) NOT NULL UNIQUE,
    Description TEXT
);

-- SpecialistSpecializations junction table
CREATE TABLE SpecialistSpecializations (
    SpecialistID INTEGER REFERENCES Specialists(SpecialistID) ON DELETE CASCADE,
    SpecializationID INTEGER REFERENCES Specializations(SpecializationID) ON DELETE CASCADE,
    PRIMARY KEY (SpecialistID, SpecializationID)
);

-- SpecialistAvailability table
CREATE TABLE SpecialistAvailability (
    AvailabilityID SERIAL PRIMARY KEY,
    SpecialistID INTEGER REFERENCES Specialists(SpecialistID) ON DELETE CASCADE,
    DayOfWeek VARCHAR(10) NOT NULL,
    StartTime TIME NOT NULL,
    EndTime TIME NOT NULL,
    IsRecurring BOOLEAN DEFAULT TRUE,
    EffectiveDate DATE NOT NULL,
    ExpiryDate DATE,
    CONSTRAINT chk_day_of_week CHECK (DayOfWeek IN ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')),
    CONSTRAINT chk_time_range CHECK (StartTime < EndTime)
);

-- Appointments table
CREATE TABLE Appointments (
    AppointmentID SERIAL PRIMARY KEY,
    UserID INTEGER REFERENCES Users(UserID) ON DELETE SET NULL,
    SpecialistID INTEGER REFERENCES Specialists(SpecialistID) ON DELETE SET NULL,
    AppointmentDateTime TIMESTAMP NOT NULL,
    EndDateTime TIMESTAMP NOT NULL,
    Status VARCHAR(20) NOT NULL DEFAULT 'scheduled',
    Type VARCHAR(20) NOT NULL,
    Notes TEXT,
    CreatedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UpdatedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_appointment_status CHECK (Status IN ('scheduled', 'completed', 'canceled', 'no-show')),
    CONSTRAINT chk_appointment_type CHECK (Type IN ('video', 'in-person', 'phone')),
    CONSTRAINT chk_appointment_time CHECK (AppointmentDateTime < EndDateTime)
);

-- Sessions table (optional implementation)
CREATE TABLE Sessions (
    SessionID SERIAL PRIMARY KEY,
    UserID INTEGER REFERENCES Users(UserID) ON DELETE SET NULL,
    StartTime TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    EndTime TIMESTAMP,
    SessionStatus VARCHAR(20) DEFAULT 'active',
    LLMProviderUsed VARCHAR(50),
    CONSTRAINT chk_session_status CHECK (SessionStatus IN ('active', 'completed', 'interrupted'))
);

-- Messages table (optional implementation)
CREATE TABLE Messages (
    MessageID SERIAL PRIMARY KEY,
    SessionID INTEGER REFERENCES Sessions(SessionID) ON DELETE SET NULL,
    SenderType VARCHAR(10) NOT NULL,
    Content TEXT NOT NULL,
    Timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    DetectedTopics JSONB,
    CONSTRAINT chk_sender_type CHECK (SenderType IN ('user', 'assistant'))
);

-- UserTopics junction table
CREATE TABLE UserTopics (
    UserID INTEGER REFERENCES Users(UserID) ON DELETE CASCADE,
    TopicID INTEGER REFERENCES Topics(TopicID) ON DELETE CASCADE,
    Timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (UserID, TopicID)
);

-- Feedback table
CREATE TABLE Feedback (
    FeedbackID SERIAL PRIMARY KEY,
    UserID INTEGER REFERENCES Users(UserID) ON DELETE SET NULL,
    Category VARCHAR(50) NOT NULL,
    RelatedID INTEGER,  -- Could refer to SessionID, AppointmentID, or SpecialistID
    Rating INTEGER NOT NULL,
    Comments TEXT,
    Timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_rating_range CHECK (Rating BETWEEN 1 AND 5),
    CONSTRAINT chk_feedback_category CHECK (Category IN ('ai-interaction', 'specialist-session', 'app-experience'))
);

-- AuditLogs table
CREATE TABLE AuditLogs (
    LogID SERIAL PRIMARY KEY,
    Timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UserID INTEGER REFERENCES Users(UserID) ON DELETE SET NULL,
    ActionType VARCHAR(50) NOT NULL,
    Description TEXT,
    IPAddress VARCHAR(45)
);

-- Extensions table for topic-specific prompt extensions
CREATE TABLE Extensions (
    ExtensionID SERIAL PRIMARY KEY,
    TopicID INTEGER REFERENCES Topics(TopicID) ON DELETE CASCADE,
    Content TEXT NOT NULL,
    Version VARCHAR(20) NOT NULL,
    LastUpdated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Add PostgreSQL-specific triggers for updated timestamps
CREATE OR REPLACE FUNCTION update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.UpdatedAt = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_appointment_modtime
BEFORE UPDATE ON Appointments
FOR EACH ROW EXECUTE FUNCTION update_modified_column();

-- Indexes for performance optimization
CREATE INDEX idx_user_email ON Users(Email);
CREATE INDEX idx_specialist_isactive ON Specialists(IsActive);
CREATE INDEX idx_appointments_datetime ON Appointments(AppointmentDateTime);
CREATE INDEX idx_appointments_status ON Appointments(Status);
CREATE INDEX idx_sessions_user ON Sessions(UserID);
CREATE INDEX idx_messages_session ON Messages(SessionID);
CREATE INDEX idx_specialist_availability ON SpecialistAvailability(SpecialistID, DayOfWeek);
CREATE INDEX idx_feedback_user ON Feedback(UserID);
CREATE INDEX idx_auditlogs_user_action ON AuditLogs(UserID, ActionType);
