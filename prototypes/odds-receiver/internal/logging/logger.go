// internal/logging/logger.go
package logging

import (
	"fmt"
	"log"
	"os"
	"runtime"
)

// Logger defines a simple logging interface
type Logger interface {
	Debug(format string, v ...interface{})
	Info(format string, v ...interface{})
	Warn(format string, v ...interface{})
	Error(format string, v ...interface{})
	ErrorWithStack(format string, v ...interface{})
}

// StandardLogger implements Logger using standard log package
type StandardLogger struct {
	debugLog *log.Logger
	infoLog  *log.Logger
	warnLog  *log.Logger
	errorLog *log.Logger
}

// NewStandardLogger creates a new StandardLogger
func NewStandardLogger() *StandardLogger {
	return &StandardLogger{
		debugLog: log.New(os.Stdout, "DEBUG: ", log.Ldate|log.Ltime|log.Lshortfile),
		infoLog:  log.New(os.Stdout, "INFO: ", log.Ldate|log.Ltime),
		warnLog:  log.New(os.Stdout, "WARN: ", log.Ldate|log.Ltime|log.Lshortfile),
		errorLog: log.New(os.Stderr, "ERROR: ", log.Ldate|log.Ltime|log.Lshortfile),
	}
}

// Debug logs debug messages
func (l *StandardLogger) Debug(format string, v ...interface{}) {
	l.debugLog.Printf(format, v...)
}

// Info logs info messages
func (l *StandardLogger) Info(format string, v ...interface{}) {
	l.infoLog.Printf(format, v...)
}

// Warn logs warning messages
func (l *StandardLogger) Warn(format string, v ...interface{}) {
	l.warnLog.Printf(format, v...)
}

// Error logs error messages
func (l *StandardLogger) Error(format string, v ...interface{}) {
	l.errorLog.Printf(format, v...)
}

func (l *StandardLogger) ErrorWithStack(format string, v ...interface{}) {
	buf := make([]byte, 8192)
	n := runtime.Stack(buf, false)
	l.errorLog.Printf("%s\nStack trace:\n%s", fmt.Sprintf(format, v...), buf[:n])
}
