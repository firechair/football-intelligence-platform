package filemanager

import (
	"fmt"
	"strings"
	"testing"
)

type quietLogger struct{}

func (quietLogger) Debug(string, ...interface{})          {}
func (quietLogger) Info(string, ...interface{})           {}
func (quietLogger) Warn(string, ...interface{})           {}
func (quietLogger) Error(string, ...interface{})          {}
func (quietLogger) ErrorWithStack(string, ...interface{}) {}

// The provider can push several files at once.
func TestPushesSavedInTheSameMillisecondAreAllKept(t *testing.T) {
	fm, err := NewFileManager(t.TempDir(), quietLogger{})
	if err != nil {
		t.Fatal(err)
	}
	for i := 0; i < 10; i++ {
		if _, err := fm.SaveData([]byte(fmt.Sprintf(`<x n="%d"/>`, i)), false); err != nil {
			t.Fatal(err)
		}
		if _, err := fm.SaveFile(strings.NewReader("gz"), true); err != nil {
			t.Fatal(err)
		}
	}
	files, err := fm.ListPendingFiles()
	if err != nil {
		t.Fatal(err)
	}
	if len(files) != 20 {
		t.Fatalf("%d of 20 pushes kept", len(files))
	}
}
