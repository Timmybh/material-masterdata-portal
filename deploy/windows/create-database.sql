IF DB_ID(N'masterdata') IS NULL
BEGIN
    CREATE DATABASE masterdata;
END;
GO
ALTER DATABASE masterdata SET READ_COMMITTED_SNAPSHOT ON WITH ROLLBACK IMMEDIATE;
GO
USE masterdata;
GO
IF FULLTEXTSERVICEPROPERTY('IsFullTextInstalled') <> 1
    THROW 51000, N'SQL Server chưa cài Full-Text and Semantic Extractions for Search.', 1;
GO
