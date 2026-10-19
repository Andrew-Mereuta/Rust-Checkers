//! Standard American checkers (English draughts) rules engine.
//!
//! Coordinates are zero-based. Black starts on rows 0–2, moves toward row 7,
//! and plays first. Red starts on rows 5–7 and moves toward row 0. Captures
//! are mandatory; a move includes every jump. Crowning ends the turn.

pub const BOARD_SIZE: usize = 8;
pub type Board = [[Option<Piece>; BOARD_SIZE]; BOARD_SIZE];

#[derive(Clone, Copy, Debug, Eq, PartialEq, Hash)]
pub enum Player {
    Red,
    Black,
}

impl Player {
    #[must_use]
    pub const fn opponent(self) -> Self {
        match self {
            Self::Red => Self::Black,
            Self::Black => Self::Red,
        }
    }

    const fn king_row(self) -> usize {
        match self {
            Self::Red => 0,
            Self::Black => BOARD_SIZE - 1,
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Hash)]
pub enum Rank {
    Man,
    King,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Hash)]
pub struct Piece {
    pub player: Player,
    pub rank: Rank,
}

impl Piece {
    #[must_use]
    pub const fn man(player: Player) -> Self {
        Self {
            player,
            rank: Rank::Man,
        }
    }
    #[must_use]
    pub const fn king(player: Player) -> Self {
        Self {
            player,
            rank: Rank::King,
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Hash)]
pub struct Position {
    pub row: usize,
    pub col: usize,
}

impl Position {
    #[must_use]
    pub const fn new(row: usize, col: usize) -> Option<Self> {
        if row < BOARD_SIZE && col < BOARD_SIZE {
            Some(Self { row, col })
        } else {
            None
        }
    }

    fn offset(self, dr: isize, dc: isize) -> Option<Self> {
        Self::new(
            self.row.checked_add_signed(dr)?,
            self.col.checked_add_signed(dc)?,
        )
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Move {
    pub path: Vec<Position>,
}

impl Move {
    #[must_use]
    pub fn new(path: Vec<Position>) -> Self {
        Self { path }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum GameStatus {
    InProgress,
    Won(Player),
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum MoveError {
    GameOver,
    IllegalMove,
}

impl std::fmt::Display for MoveError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::GameOver => write!(f, "the game is over"),
            Self::IllegalMove => write!(f, "illegal move"),
        }
    }
}
impl std::error::Error for MoveError {}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Game {
    board: Board,
    turn: Player,
    status: GameStatus,
}

impl Default for Game {
    fn default() -> Self {
        Self::new()
    }
}

impl Game {
    #[must_use]
    pub fn new() -> Self {
        let mut board = [[None; BOARD_SIZE]; BOARD_SIZE];
        for (row, squares) in board.iter_mut().enumerate() {
            let player = match row {
                0..=2 => Some(Player::Black),
                5..=7 => Some(Player::Red),
                _ => None,
            };
            if let Some(player) = player {
                for (col, square) in squares.iter_mut().enumerate() {
                    if (row + col) % 2 == 1 {
                        *square = Some(Piece::man(player));
                    }
                }
            }
        }
        Self {
            board,
            turn: Player::Black,
            status: GameStatus::InProgress,
        }
    }

    /// Constructs a game from a valid custom board and computes its status.
    #[must_use]
    pub fn from_board(board: Board, turn: Player) -> Self {
        let status = if moves_for(&board, turn).is_empty() {
            GameStatus::Won(turn.opponent())
        } else {
            GameStatus::InProgress
        };
        Self {
            board,
            turn,
            status,
        }
    }

    #[must_use]
    pub const fn board(&self) -> &Board {
        &self.board
    }

    #[must_use]
    pub fn piece_at(&self, position: Position) -> Option<Piece> {
        self.board
            .get(position.row)
            .and_then(|row| row.get(position.col))
            .copied()
            .flatten()
    }

    #[must_use]
    pub const fn current_player(&self) -> Player {
        self.turn
    }

    #[must_use]
    pub const fn status(&self) -> GameStatus {
        self.status
    }

    #[must_use]
    pub fn legal_moves(&self) -> Vec<Move> {
        if self.status == GameStatus::InProgress {
            moves_for(&self.board, self.turn)
        } else {
            Vec::new()
        }
    }

    /// Applies a complete legal move. Errors leave the game unchanged.
    pub fn apply_move(&mut self, requested: &Move) -> Result<(), MoveError> {
        if self.status != GameStatus::InProgress {
            return Err(MoveError::GameOver);
        }
        if !self.legal_moves().contains(requested) {
            return Err(MoveError::IllegalMove);
        }

        let start = requested.path[0];
        let end = *requested
            .path
            .last()
            .expect("legal moves have a destination");
        let mut piece = self.board[start.row][start.col]
            .take()
            .expect("legal moves start at a piece");
        for pair in requested.path.windows(2) {
            if pair[0].row.abs_diff(pair[1].row) == 2 {
                let middle = Position {
                    row: (pair[0].row + pair[1].row) / 2,
                    col: (pair[0].col + pair[1].col) / 2,
                };
                self.board[middle.row][middle.col] = None;
            }
        }
        if end.row == piece.player.king_row() {
            piece.rank = Rank::King;
        }
        self.board[end.row][end.col] = Some(piece);
        self.turn = self.turn.opponent();
        if moves_for(&self.board, self.turn).is_empty() {
            self.status = GameStatus::Won(self.turn.opponent());
        }
        Ok(())
    }
}

fn directions(piece: Piece) -> &'static [(isize, isize)] {
    const BLACK: &[(isize, isize)] = &[(1, -1), (1, 1)];
    const RED: &[(isize, isize)] = &[(-1, -1), (-1, 1)];
    const KING: &[(isize, isize)] = &[(-1, -1), (-1, 1), (1, -1), (1, 1)];
    match piece.rank {
        Rank::King => KING,
        Rank::Man => match piece.player {
            Player::Black => BLACK,
            Player::Red => RED,
        },
    }
}

fn moves_for(board: &Board, player: Player) -> Vec<Move> {
    let mut captures = Vec::new();
    let mut steps = Vec::new();
    for (row, squares) in board.iter().enumerate() {
        for (col, square) in squares.iter().enumerate() {
            let Some(piece) = square.filter(|piece| piece.player == player) else {
                continue;
            };
            let start = Position { row, col };
            capture_paths(board, start, piece, &mut vec![start], &mut captures);
            for &(dr, dc) in directions(piece) {
                if let Some(end) = start.offset(dr, dc)
                    && board[end.row][end.col].is_none()
                {
                    steps.push(Move::new(vec![start, end]));
                }
            }
        }
    }
    if captures.is_empty() { steps } else { captures }
}

fn capture_paths(
    board: &Board,
    current: Position,
    piece: Piece,
    path: &mut Vec<Position>,
    moves: &mut Vec<Move>,
) {
    let mut extended = false;
    for &(dr, dc) in directions(piece) {
        let (Some(middle), Some(end)) = (current.offset(dr, dc), current.offset(2 * dr, 2 * dc))
        else {
            continue;
        };
        if board[middle.row][middle.col].is_some_and(|victim| victim.player != piece.player)
            && board[end.row][end.col].is_none()
        {
            extended = true;
            let mut next = *board;
            next[current.row][current.col] = None;
            next[middle.row][middle.col] = None;
            next[end.row][end.col] = Some(piece);
            path.push(end);
            if piece.rank == Rank::Man && end.row == piece.player.king_row() {
                moves.push(Move::new(path.clone()));
            } else {
                capture_paths(&next, end, piece, path, moves);
            }
            path.pop();
        }
    }
    if !extended && path.len() > 1 {
        moves.push(Move::new(path.clone()));
    }
}
