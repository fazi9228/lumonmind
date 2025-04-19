# LumonMind Database Documentation

## Overview

This document provides details about the LumonMind application database structure, designed to support a mental health chatbot platform with therapist appointment booking capabilities.

## Database Schema

The database follows a relational model with PostgreSQL as the RDBMS. Key components include:

### Core Tables

1. **Users**
   - Stores information about both registered users and guests
   - Primary identifier: `UserID`
   - Contains basic contact information and preferences

2. **Specialists**
   - Contains therapist/counselor information
   - Primary identifier: `SpecialistID`
   - Stores credentials, biography, and hourly rates

3. **Appointments**
   - Records scheduled meetings between users and specialists
   - Tracks appointment status, type, and timestamps

4. **Topics**
   - Mental health topics for categorization
   - Contains keywords used for topic detection

5. **Specializations**
   - Areas of expertise for specialists
   - Used to match users with appropriate specialists

### Optional Components

6. **Sessions**
   - Records of conversation sessions between users and the AI
   - Optional implementation - can be excluded without affecting core functionality

7. **Messages**
   - Individual messages within sessions
   - Optional implementation - depends on privacy and data retention policies

### Junction Tables

8. **SpecialistSpecializations**
   - Connects specialists to their areas of expertise

9. **UserTopics**
   - Tracks user interests in specific mental health topics

10. **SpecialistAvailability**
    - Manages specialist scheduling and availability

### Support Tables

11. **Feedback**
    - Collects user ratings and comments on AI and specialist interactions

12. **Extensions**
    - Stores topic-specific additions to the AI prompt

13. **AuditLogs**
    - Records system activity for security and monitoring

## Entity Relationship Diagram

The database structure follows the relationships outlined in the included ERD diagram. Key relationships:

- Users can have multiple Sessions (optional)
- Users can book multiple Appointments with Specialists
- Specialists have specific Specializations and Availability
- Topics can be associated with Users and Sessions

## Installation

1. Create a PostgreSQL database for LumonMind
2. Run the provided schema creation script (`schema.sql`)
3. Verify all tables and relationships were created successfully

## Common Queries

The repository includes sample queries for:

- Retrieving user appointments with specialist details
- Finding available specialists by specialization
- Getting specialist availability for scheduling
- Generating comprehensive user activity reports

## Master Dashboard Query

A consolidated query is provided for reporting and dashboard creation, which joins all key tables to provide a comprehensive view of system activity.

## Maintenance Notes

- Indexes have been added for common query patterns
- A trigger automatically updates timestamp fields
- Foreign key constraints are set to maintain data integrity while keeping session storage optional

## Privacy Considerations

- The database is designed to support various data retention policies
- Personal data is primarily stored in the Users table
- Session and message data can be omitted without affecting appointment functionality
