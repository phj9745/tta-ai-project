export interface DriveProject {
  id: string
  name: string
  createdTime?: string
  modifiedTime?: string
}

export interface DriveAccount {
  googleId: string
  displayName: string
  email?: string | null
}

export interface DriveSetupResponse {
  folderCreated: boolean
  folderId: string
  folderName: string
  projects: DriveProject[]
  account?: DriveAccount
}
