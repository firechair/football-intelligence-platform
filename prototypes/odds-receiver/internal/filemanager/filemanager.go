// internal/filemanager/filemanager.go
package filemanager

import (
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"github.com/firechair/odds-receiver/internal/logging"
)

// FileManager handles file operations for XML data
type FileManager struct {
	baseDir      string
	parsedDir    string
	logger       logging.Logger
	processMutex sync.Map // Maps file paths to mutexes to prevent concurrent processing
}

// NewFileManager creates a new FileManager
func NewFileManager(baseDir string, logger logging.Logger) (*FileManager, error) {
	// Create base directory if it doesn't exist
	if err := os.MkdirAll(baseDir, 0755); err != nil {
		return nil, fmt.Errorf("failed to create base directory: %w", err)
	}

	// Create parsed directory if it doesn't exist
	parsedDir := filepath.Join(baseDir, "parsed")
	if err := os.MkdirAll(parsedDir, 0755); err != nil {
		return nil, fmt.Errorf("failed to create parsed directory: %w", err)
	}

	return &FileManager{
		baseDir:   baseDir,
		parsedDir: parsedDir,
		logger:    logger,
	}, nil
}

// SaveFile saves the received data to a file and returns the file path
func (fm *FileManager) SaveFile(data io.Reader, isGzipped bool) (string, error) {
	// Generate a unique filename with timestamp
	timestamp := time.Now().Format("20060102-150405.000")
	var filename string
	if isGzipped {
		filename = fmt.Sprintf("odds_%s.xml.gz", timestamp)
	} else {
		filename = fmt.Sprintf("odds_%s.xml", timestamp)
	}

	filePath := filepath.Join(fm.baseDir, filename)

	// Create the file
	file, err := os.Create(filePath)
	if err != nil {
		return "", fmt.Errorf("failed to create file: %w", err)
	}
	defer file.Close()

	// Copy the data to the file
	if _, err := io.Copy(file, data); err != nil {
		return "", fmt.Errorf("failed to write to file: %w", err)
	}

	fm.logger.Info("Saved received data to file: %s", filePath)
	return filePath, nil
}

// MarkFileAsParsed moves the file to the parsed directory
func (fm *FileManager) MarkFileAsParsed(filePath string) error {
	// Get the filename
	filename := filepath.Base(filePath)

	// Create the destination path
	destPath := filepath.Join(fm.parsedDir, filename)

	// Move the file
	if err := os.Rename(filePath, destPath); err != nil {
		return fmt.Errorf("failed to move file to parsed directory: %w", err)
	}

	fm.logger.Info("Moved file to parsed directory: %s", destPath)
	return nil
}

// LockFileForProcessing acquires a lock for the file to prevent concurrent processing
func (fm *FileManager) LockFileForProcessing(filePath string) func() {
	// Get or create a mutex for this file
	var mutex sync.Mutex
	actual, _ := fm.processMutex.LoadOrStore(filePath, &mutex)
	mtx := actual.(*sync.Mutex)

	// Lock the mutex
	mtx.Lock()

	// Return a function that unlocks the mutex and removes it from the map
	return func() {
		mtx.Unlock()
		fm.processMutex.Delete(filePath)
	}
}

// ListPendingFiles returns a list of files that haven't been processed yet
func (fm *FileManager) ListPendingFiles() ([]string, error) {
	var pendingFiles []string

	// Read the base directory
	entries, err := os.ReadDir(fm.baseDir)
	if err != nil {
		return nil, fmt.Errorf("failed to read directory: %w", err)
	}

	// Filter out directories
	for _, entry := range entries {
		if entry.IsDir() {
			continue
		}

		// Include only XML and gzipped XML files
		name := entry.Name()
		ext := filepath.Ext(name)
		if ext == ".xml" || ext == ".gz" {
			pendingFiles = append(pendingFiles, filepath.Join(fm.baseDir, name))
		}
	}

	return pendingFiles, nil
}

// CleanupOldParsedFiles removes processed files older than the specified duration
func (fm *FileManager) CleanupOldParsedFiles(maxAge time.Duration) error {
	// Read the parsed directory
	entries, err := os.ReadDir(fm.parsedDir)
	if err != nil {
		return fmt.Errorf("failed to read parsed directory: %w", err)
	}

	// Current time
	now := time.Now()

	// Keep track of deleted files to log a summary
	deletedCount := 0
	successCount := 0

	// Check each file's age
	for _, entry := range entries {
		if entry.IsDir() {
			continue
		}

		filePath := filepath.Join(fm.parsedDir, entry.Name())

		// Check if this is a success marker file
		isSuccessFile := strings.HasSuffix(filePath, ".success")

		// Get file info to check modification time
		info, err := entry.Info()
		if err != nil {
			fm.logger.Warn("Failed to get file info for %s: %v", entry.Name(), err)
			continue
		}

		// If the file is older than maxAge, delete it
		if now.Sub(info.ModTime()) > maxAge {
			if err := os.Remove(filePath); err != nil {
				fm.logger.Warn("Failed to remove old parsed file %s: %v", filePath, err)
				continue
			}

			if isSuccessFile {
				successCount++
			} else {
				deletedCount++

				// Also delete the corresponding .success file if it exists
				successFilePath := filePath + ".success"
				if _, err := os.Stat(successFilePath); err == nil {
					if err := os.Remove(successFilePath); err != nil {
						fm.logger.Warn("Failed to remove success marker file %s: %v", successFilePath, err)
					} else {
						successCount++
					}
				}
			}
		}
	}

	fm.logger.Info("Cleanup completed: removed %d parsed files and %d success markers older than %v",
		deletedCount, successCount, maxAge)
	return nil
}

// GetFileStats returns statistics about pending and processed files
func (fm *FileManager) GetFileStats() (map[string]int, error) {
	stats := map[string]int{
		"pending":   0,
		"processed": 0,
	}

	// Count pending files
	entries, err := os.ReadDir(fm.baseDir)
	if err != nil {
		return nil, fmt.Errorf("failed to read base directory: %w", err)
	}

	for _, entry := range entries {
		if !entry.IsDir() {
			stats["pending"]++
		}
	}

	// Count processed files
	entries, err = os.ReadDir(fm.parsedDir)
	if err != nil {
		return nil, fmt.Errorf("failed to read parsed directory: %w", err)
	}

	for _, entry := range entries {
		if !entry.IsDir() {
			stats["processed"]++
		}
	}

	return stats, nil
}

// SaveData saves the provided data to a file and returns the file path
func (fm *FileManager) SaveData(data []byte, isGzipped bool) (string, error) {
	// Generate a unique filename with timestamp
	timestamp := time.Now().Format("20060102-150405.000")
	var filename string
	if isGzipped {
		filename = fmt.Sprintf("odds_%s.xml.gz", timestamp)
	} else {
		filename = fmt.Sprintf("odds_%s.xml", timestamp)
	}

	filePath := filepath.Join(fm.baseDir, filename)

	// Create the file
	file, err := os.Create(filePath)
	if err != nil {
		return "", fmt.Errorf("failed to create file: %w", err)
	}
	defer file.Close()

	// Write the data to the file
	if _, err := file.Write(data); err != nil {
		return "", fmt.Errorf("failed to write to file: %w", err)
	}

	fm.logger.Info("Saved received data to file: %s", filePath)
	return filePath, nil
}

func (fm *FileManager) MarkFileAsSuccessfullyProcessed(filePath string) error {
	// Create a success marker file next to the parsed file
	parsedPath := filepath.Join(fm.parsedDir, filepath.Base(filePath))
	successMarkerPath := parsedPath + ".success"

	file, err := os.Create(successMarkerPath)
	if err != nil {
		return fmt.Errorf("failed to create success marker: %w", err)
	}
	defer file.Close()

	return nil
}
